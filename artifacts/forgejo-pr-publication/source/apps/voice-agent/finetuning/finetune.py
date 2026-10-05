"""Fine-tuning script for FunctionGemma on CodeTether tools dataset.

This script fine-tunes Google's FunctionGemma model (google/functiongemma-270m-it)
on a dataset of CodeTether tool invocations using LoRA (Low-Rank Adaptation).

Usage:
    python finetune.py --train_file training_examples.jsonl --output_dir ./finetuned_model
    python finetune.py --train_file training_examples.jsonl --val_file val_examples.jsonl --epochs 3 --batch_size 8
"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import (
    AutoModelForCausalLM,
    AutoProcessor,
    DataCollatorForSeq2Seq,
    TrainingArguments,
    Trainer,
    TrainerCallback,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_function_call(
    output: str,
) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
    """Parse FunctionGemma output format into function name and arguments.

    Args:
        output: The raw text output from FunctionGemma.

    Returns:
        Tuple of (function_name, arguments_dict) or (None, None) if parsing fails.
    """
    start_tag = '<start_function_call>'
    end_tag = '<end_function_call>'

    start_idx = output.find(start_tag)
    end_idx = output.find(end_tag)

    if start_idx == -1 or end_idx == -1:
        return None, None

    start_idx += len(start_tag)
    function_call_str = output[start_idx:end_idx]

    if not function_call_str.startswith('call:'):
        return None, None

    function_call_str = function_call_str[5:]

    brace_start = function_call_str.find('{')
    brace_end = function_call_str.rfind('}')

    if brace_start == -1 or brace_end == -1:
        return None, None

    func_name = function_call_str[:brace_start]
    args_str = function_call_str[brace_start + 1 : brace_end]

    args = {}
    escape_token = '<escape>'

    while args_str:
        eq_idx = args_str.find(':')

        if eq_idx == -1:
            break

        arg_name = args_str[:eq_idx].strip()
        args_str = args_str[eq_idx + 1 :]

        if not args_str.startswith(escape_token):
            continue

        args_str = args_str[len(escape_token) :]
        end_escape_idx = args_str.find(escape_token)

        if end_escape_idx == -1:
            break

        arg_value = args_str[:end_escape_idx]
        args[arg_name] = arg_value
        args_str = args_str[end_escape_idx + len(escape_token) :]

        if args_str.startswith(','):
            args_str = args_str[1:].strip()

    return func_name, args


def format_function_call(tool_name: str, args: Dict[str, str]) -> str:
    """Format a function call in FunctionGemma format.

    Args:
        tool_name: The name of the function to call.
        args: Dictionary of argument names to values.

    Returns:
        Formatted function call string.
    """
    args_str = ''
    for key, value in args.items():
        args_str += f'{key}:<escape>{value}<escape>,'
    args_str = args_str.rstrip(',')
    return f'<start_function_call>call:{tool_name}{{{args_str}}}<end_function_call>'


def load_jsonl_dataset(file_path: str) -> Dataset:
    """Load a JSONL dataset file.

    Args:
        file_path: Path to the JSONL file.

    Returns:
        HuggingFace Dataset object.
    """
    examples = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data = json.loads(line)
                    examples.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(f'Failed to parse line: {e}')

    logger.info(f'Loaded {len(examples)} examples from {file_path}')
    return Dataset.from_list(examples)


def prepare_dataset(
    dataset: Dataset,
    processor: AutoProcessor,
    model: AutoModelForCausalLM,
    max_length: int = 512,
) -> Dataset:
    """Prepare dataset for training.

    Args:
        dataset: The input dataset.
        processor: The FunctionGemma processor.
        model: The FunctionGemma model.
        max_length: Maximum sequence length.

    Returns:
        Processed dataset ready for training.
    """

    def tokenize_function(examples: Dict[str, Any]) -> Dict[str, Any]:
        inputs = []
        targets = []

        for input_text, output_text in zip(
            examples['input'], examples['output']
        ):
            inputs.append(input_text)
            targets.append(output_text)

        try:
            encoded = processor(
                text=inputs,
                text_target=targets,
                padding='max_length',
                truncation=True,
                max_length=max_length,
                return_tensors='pt',
            )

            input_ids = encoded['input_ids']
            labels = encoded['labels']

            attention_mask = encoded.get('attention_mask')
            if attention_mask is None:
                attention_mask = torch.ones_like(input_ids)

            return {
                'input_ids': input_ids.tolist(),
                'labels': labels.tolist(),
                'attention_mask': attention_mask.tolist(),
            }
        except Exception as e:
            logger.error(f'Error during tokenization: {e}')
            return {
                'input_ids': [0] * max_length,
                'labels': [0] * max_length,
                'attention_mask': [0] * max_length,
            }

    logger.info('Tokenizing dataset...')
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,
        desc='Tokenizing',
    )

    return tokenized_dataset


class MetricsCallback(TrainerCallback):
    """Custom callback to log metrics during training."""

    def __init__(self):
        self.training_loss = []
        self.eval_results = []

    def on_log(self, args, state, control, model=None, logs=None, **kwargs):
        if logs:
            loss = logs.get('loss', None)
            if loss:
                self.training_loss.append(loss)
                logger.info(
                    f'Step {state.global_step}: Training Loss = {loss:.4f}'
                )


def compute_metrics(eval_pred, processor, model):
    """Compute evaluation metrics.

    Args:
        eval_pred: Tuple of predictions and labels.
        processor: The FunctionGemma processor.
        model: The FunctionGemma model.

    Returns:
        Dictionary of metrics.
    """
    predictions, labels = eval_pred

    predictions_str = processor.batch_decode(
        predictions, skip_special_tokens=True
    )
    labels_str = processor.batch_decode(labels, skip_special_tokens=True)

    exact_matches = 0
    function_correct = 0
    total = len(predictions_str)

    for pred, label in zip(predictions_str, labels_str):
        pred_name, pred_args = parse_function_call(pred)
        label_name, label_args = parse_function_call(label)

        if pred_name == label_name:
            function_correct += 1

        if pred.strip() == label.strip():
            exact_matches += 1

    metrics = {
        'exact_match': exact_matches / total if total > 0 else 0,
        'function_accuracy': function_correct / total if total > 0 else 0,
    }

    return metrics


def fine_tune_functiongemma(
    model_path: str = 'google/functiongemma-270m-it',
    train_file: str = 'training_examples.jsonl',
    val_file: Optional[str] = None,
    output_dir: str = './finetuned_model',
    epochs: int = 3,
    batch_size: int = 4,
    learning_rate: float = 3e-4,
    max_length: int = 512,
    lora_r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.1,
    warmup_steps: int = 100,
    weight_decay: float = 0.01,
    fp16: bool = True,
    gradient_accumulation_steps: int = 4,
    eval_strategy: str = 'epoch',
    save_strategy: str = 'epoch',
    logging_steps: int = 10,
    save_total_limit: int = 2,
) -> Dict[str, Any]:
    """Fine-tune FunctionGemma on the CodeTether tools dataset.

    Args:
        model_path: Path to the base FunctionGemma model.
        train_file: Path to the training JSONL file.
        val_file: Optional path to the validation JSONL file.
        output_dir: Directory to save the fine-tuned model.
        epochs: Number of training epochs.
        batch_size: Training batch size.
        learning_rate: Learning rate.
        max_length: Maximum sequence length.
        lora_r: LoRA rank.
        lora_alpha: LoRA alpha parameter.
        lora_dropout: LoRA dropout probability.
        warmup_steps: Number of warmup steps.
        weight_decay: Weight decay coefficient.
        fp16: Whether to use FP16 precision.
        gradient_accumulation_steps: Gradient accumulation steps.
        eval_strategy: Evaluation strategy ('epoch', 'steps', or 'no').
        save_strategy: Model save strategy.
        logging_steps: Logging interval.
        save_total_limit: Maximum number of saved checkpoints.

    Returns:
        Dictionary containing training results and metrics.
    """
    logger.info('Loading base model and processor...')

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f'Using device: {device}')

    try:
        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=True,
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16
            if fp16 and device.type == 'cuda'
            else torch.float32,
            device_map='auto' if device.type == 'cuda' else None,
            trust_remote_code=True,
        )

        if device.type == 'cpu':
            model = model.to(device)

        logger.info('Model loaded successfully')

    except Exception as e:
        logger.error(f'Failed to load model: {e}')
        raise RuntimeError(f'Model loading failed: {e}')

    logger.info('Configuring LoRA...')
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'],
        bias='none',
        inference_mode=False,
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    logger.info('Loading training data...')
    train_dataset = load_jsonl_dataset(train_file)

    val_dataset = None
    if val_file and os.path.exists(val_file):
        logger.info('Loading validation data...')
        val_dataset = load_jsonl_dataset(val_file)

    logger.info('Preparing datasets for training...')
    train_dataset = prepare_dataset(train_dataset, processor, model, max_length)

    if val_dataset:
        val_dataset = prepare_dataset(val_dataset, processor, model, max_length)

    data_collator = DataCollatorForSeq2Seq(
        processor.tokenizer,
        model=model,
        padding='max_length',
        max_length=max_length,
    )

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        warmup_steps=warmup_steps,
        weight_decay=weight_decay,
        learning_rate=learning_rate,
        fp16=fp16 and device.type == 'cuda',
        logging_dir=f'{output_dir}/logs',
        logging_steps=logging_steps,
        eval_strategy=eval_strategy if val_dataset else 'no',
        save_strategy=save_strategy,
        save_total_limit=save_total_limit,
        load_best_model_at_end=True if val_dataset else False,
        metric_for_best_model='eval_loss' if val_dataset else None,
        greater_is_better=False,
        report_to='none',
        remove_unused_columns=False,
        no_cuda=device.type == 'cpu',
    )

    metrics_callback = MetricsCallback()

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
        callbacks=[metrics_callback],
    )

    logger.info('Starting training...')
    train_result = trainer.train()

    training_loss = train_result.training_loss
    logger.info(f'Training completed. Final training loss: {training_loss:.4f}')

    logger.info(f'Saving model to {output_dir}...')
    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)

    metrics = {
        'training_loss': training_loss,
        'training_steps': train_result.global_step,
        'model_path': output_dir,
    }

    if val_dataset:
        eval_results = trainer.evaluate()
        metrics['eval_loss'] = eval_results.get('eval_loss', None)
        metrics['eval_metrics'] = eval_results

    logger.info('Fine-tuning completed successfully!')
    logger.info(f'Results: {metrics}')

    return metrics


def evaluate_model(
    model_path: str,
    test_file: str,
    output_path: Optional[str] = None,
) -> Dict[str, float]:
    """Evaluate a fine-tuned model on a test dataset.

    Args:
        model_path: Path to the fine-tuned model.
        test_file: Path to the test JSONL file.
        output_path: Optional path to save evaluation results.

    Returns:
        Dictionary of evaluation metrics.
    """
    logger.info(f'Loading model from {model_path}...')

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    processor = AutoProcessor.from_pretrained(
        model_path, trust_remote_code=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16 if device.type == 'cuda' else torch.float32,
        device_map='auto' if device.type == 'cuda' else None,
        trust_remote_code=True,
    )

    if device.type == 'cpu':
        model = model.to(device)

    logger.info(f'Loading test data from {test_file}...')
    test_dataset = load_jsonl_dataset(test_file)

    model.eval()

    total = 0
    exact_matches = 0
    function_correct = 0

    logger.info('Evaluating model...')
    for example in tqdm(test_dataset, desc='Evaluating'):
        user_input = example['input']
        expected_output = example['output']

        try:
            messages = [{'role': 'user', 'content': user_input}]

            input_text = processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

            inputs = processor(
                input_text,
                return_tensors='pt',
            ).to(model.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    temperature=None,
                    top_p=None,
                )

            generated_text = processor.decode(
                outputs[0], skip_special_tokens=False
            )

            pred_name, pred_args = parse_function_call(generated_text)
            expected_name, expected_args = parse_function_call(expected_output)

            if pred_name == expected_name:
                function_correct += 1

            if generated_text.strip() == expected_output.strip():
                exact_matches += 1

            total += 1

        except Exception as e:
            logger.error(f'Error evaluating example: {e}')
            total += 1

    metrics = {
        'exact_match_accuracy': exact_matches / total if total > 0 else 0,
        'function_accuracy': function_correct / total if total > 0 else 0,
        'total_examples': total,
        'exact_matches': exact_matches,
        'function_correct': function_correct,
    }

    logger.info(f'Evaluation Results:')
    logger.info(
        f'  Exact Match Accuracy: {metrics["exact_match_accuracy"]:.4f}'
    )
    logger.info(f'  Function Accuracy: {metrics["function_accuracy"]:.4f}')
    logger.info(f'  Total Examples: {metrics["total_examples"]}')

    if output_path:
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        logger.info(f'Results saved to {output_path}')

    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Fine-tune FunctionGemma on CodeTether tools dataset'
    )

    parser.add_argument(
        '--model_path',
        type=str,
        default='google/functiongemma-270m-it',
        help='Path to the base FunctionGemma model',
    )
    parser.add_argument(
        '--train_file',
        type=str,
        default='training_examples.jsonl',
        help='Path to the training JSONL file',
    )
    parser.add_argument(
        '--val_file',
        type=str,
        default=None,
        help='Path to the validation JSONL file (optional)',
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        default='./finetuned_model',
        help='Directory to save the fine-tuned model',
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=3,
        help='Number of training epochs',
    )
    parser.add_argument(
        '--batch_size',
        type=int,
        default=4,
        help='Training batch size',
    )
    parser.add_argument(
        '--learning_rate',
        type=float,
        default=3e-4,
        help='Learning rate',
    )
    parser.add_argument(
        '--max_length',
        type=int,
        default=512,
        help='Maximum sequence length',
    )
    parser.add_argument(
        '--lora_r',
        type=int,
        default=16,
        help='LoRA rank',
    )
    parser.add_argument(
        '--lora_alpha',
        type=int,
        default=32,
        help='LoRA alpha parameter',
    )
    parser.add_argument(
        '--lora_dropout',
        type=float,
        default=0.1,
        help='LoRA dropout probability',
    )
    parser.add_argument(
        '--evaluate',
        action='store_true',
        help='Run evaluation instead of training',
    )
    parser.add_argument(
        '--test_file',
        type=str,
        default=None,
        help='Path to test file for evaluation',
    )

    args = parser.parse_args()

    if args.evaluate:
        if not args.test_file:
            parser.error('--test_file is required for evaluation')

        if not os.path.exists(args.output_dir):
            parser.error(f'Model path {args.output_dir} does not exist')

        evaluate_model(
            model_path=args.output_dir,
            test_file=args.test_file,
        )
    else:
        fine_tune_functiongemma(
            model_path=args.model_path,
            train_file=args.train_file,
            val_file=args.val_file,
            output_dir=args.output_dir,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            max_length=args.max_length,
            lora_r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
        )
