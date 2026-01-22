'use client'

import { Container } from '@/components/Container'

const faqs = [
    [
        {
            question: 'How is this different from ChatGPT?',
            answer: 'ChatGPT is a chat interface. CodeTether is a task runner. You trigger a webhook, AI works in the background, and you get real files via email or callback.',
        },
        {
            question: 'What is RLM?',
            answer: 'RLM (Recursive Language Models) is MIT research that treats your input as an environment variable, not direct LLM context. Instead of stuffing everything into one prompt, RLM recursively decomposes tasks, processes chunks independently, verifies results, and stitches them together.',
        },
        {
            question: 'Can I trigger tasks from Zapier/n8n/Make?',
            answer: 'Yes. CodeTether provides webhook endpoints that work with any automation platform. Results come back via webhook callback or email.',
        },
    ],
    [
        {
            question: 'Why can CodeTether handle longer tasks than ChatGPT?',
            answer: 'Regular LLMs suffer from "context rot"—quality degrades as input grows. GPT-5 scores 0% on tasks with 6-11M tokens. CodeTether uses RLM architecture to handle these same tasks with 91% accuracy by processing recursively instead of all at once.',
        },
        {
            question: 'How do I get the output?',
            answer: 'Three ways: (1) Email with file attachments, (2) Webhook callback with JSON, (3) Dashboard download. Reply to emails to refine results.',
        },
        {
            question: 'What if a task fails?',
            answer: 'You get notified with error details. Tasks checkpoint progress so partial work isn\'t lost. Pro plan includes priority support.',
        },
    ],
    [
        {
            question: 'Is there a limit to how much data I can process?',
            answer: 'CodeTether handles 10M+ tokens—100x more than typical LLMs. RLM architecture recursively breaks down massive inputs, processes them in chunks, and reconstructs verified results. Cost stays comparable to base model pricing.',
        },
        {
            question: 'Can I self-host?',
            answer: 'Yes. CodeTether is open source (Apache 2.0). Run it on your own servers with full control. Docker images and Helm charts provided.',
        },
        {
            question: 'What support is included?',
            answer: 'Free: Community Discord. Pro: Priority email (24hr response). Agency: Onboarding call and dedicated support.',
        },
    ],
]

export function Faqs() {
    return (
        <section
            id="faqs"
            aria-labelledby="faqs-title"
            className="border-t border-gray-200 dark:border-gray-800 py-20 sm:py-32 bg-white dark:bg-gray-950"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0">
                    <h2
                        id="faqs-title"
                        className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white"
                    >
                        Frequently Asked Questions
                    </h2>
                </div>
                <ul
                    role="list"
                    className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 sm:mt-20 lg:max-w-none lg:grid-cols-3"
                >
                    {faqs.map((column, columnIndex) => (
                        <li key={columnIndex}>
                            <ul role="list" className="space-y-10">
                                {column.map((faq, faqIndex) => (
                                    <li key={faqIndex}>
                                        <h3 className="text-lg/6 font-semibold text-gray-900 dark:text-white">
                                            {faq.question}
                                        </h3>
                                        <p className="mt-4 text-sm text-gray-600 dark:text-gray-400">{faq.answer}</p>
                                    </li>
                                ))}
                            </ul>
                        </li>
                    ))}
                </ul>
            </Container>
        </section>
    )
}
