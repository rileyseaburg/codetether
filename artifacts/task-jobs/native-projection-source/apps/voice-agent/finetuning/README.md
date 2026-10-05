# FunctionGemma Fine-Tuning for CodeTether Tools

This directory contains the dataset and scripts for fine-tuning Google's FunctionGemma model on CodeTether tool invocations.

## Files

- `codetether_tools.json` - JSON schema for all 8 CodeTether tools in FunctionGemma format
- `training_examples.jsonl` - Training examples (68 examples) in JSONL format
- `generate_dataset.py` - Script to generate additional training examples
- `finetune.py` - Script to fine-tune FunctionGemma using LoRA
- `requirements.txt` - Python dependencies for fine-tuning

## CodeTether Tools

1. **create_task** - Create a new task with title, description, optional codebase_id, agent_type, and priority
2. **list_tasks** - List tasks with optional status and codebase_id filters
3. **get_task** - Get details of a specific task by ID
4. **cancel_task** - Cancel an active task by ID
5. **get_session_history** - Retrieve message history for a session
6. **playback_session** - Play back a session with verbatim or summary style
7. **discover_agents** - List available agents in the system
8. **send_message** - Send a message to a specific agent

## Usage

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Generate Additional Training Examples

```bash
python generate_dataset.py --output training_examples.jsonl
python generate_dataset.py --create-task 100 --list-tasks 50 --get-task 50 --output expanded_dataset.jsonl
```

### Fine-tune the Model

```bash
python finetune.py \
    --train_file training_examples.jsonl \
    --val_file val_examples.jsonl \
    --output_dir ./finetuned_model \
    --epochs 3 \
    --batch_size 4 \
    --learning_rate 3e-4
```

### Evaluate the Fine-tuned Model

```bash
python finetune.py --evaluate \
    --model_path ./finetuned_model \
    --test_file test_examples.jsonl
```

## FunctionGemma Output Format

The model outputs function calls in this format:

```
<start_function_call>call:func_name{arg1:<escape>value1<escape>,arg2:<escape>value2<escape>}<end_function_call>
```

## Dataset Format

Each line in the JSONL file contains:

```json
{"input": "user query in natural language", "output": "<start_function_call>call:func_name{args}<end_function_call>"}
```

## Model Configuration

The fine-tuning uses:
- Base model: `google/functiongemma-270m-it`
- Method: LoRA (Low-Rank Adaptation)
- LoRA rank: 16
- LoRA alpha: 32
- Target modules: q_proj, k_proj, v_proj, o_proj
- Learning rate: 3e-4
- Batch size: 4 (effective 16 with gradient accumulation)
- Max sequence length: 512

## Hardware Requirements

- GPU with at least 8GB VRAM (recommended 16GB+)
- CUDA 11.8+ or ROCm 5.4+
- 16GB+ system RAM

## Training Time

On a single GPU:
- ~30-60 minutes for 3 epochs with the default dataset size
- Adjust batch size and gradient accumulation based on your GPU memory
