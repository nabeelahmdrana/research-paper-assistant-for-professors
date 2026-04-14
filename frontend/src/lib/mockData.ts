import type { Paper, QueryResult, DbStats } from "./types";

export const MOCK_PAPERS: Paper[] = [
  {
    id: "1",
    title: "Attention Is All You Need",
    authors: ["Vaswani", "Shazeer", "Parmar", "Uszkoreit", "Jones"],
    year: 2017,
    source: "pdf",
    abstract:
      "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder.",
    dateAdded: "2026-04-09T10:00:00Z",
    doi: "10.48550/arXiv.1706.03762",
  },
  {
    id: "2",
    title:
      "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
    authors: ["Devlin", "Chang", "Lee", "Toutanova"],
    year: 2018,
    source: "doi",
    abstract:
      "We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers.",
    dateAdded: "2026-04-06T14:30:00Z",
    doi: "10.48550/arXiv.1810.04805",
  },
  {
    id: "3",
    title:
      "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
    authors: ["Wei", "Wang", "Schuurmans", "Bosma", "Ichter", "Xia"],
    year: 2022,
    source: "arxiv",
    abstract:
      "We explore how generating a chain of thought—a series of intermediate reasoning steps—significantly improves the ability of large language models to perform complex reasoning.",
    dateAdded: "2026-04-04T09:15:00Z",
    url: "https://arxiv.org/abs/2201.11903",
  },
];

export const MOCK_QUERIES: QueryResult[] = [
  {
    id: "q1",
    question: "What is the state of transformer architectures in NLP?",
    createdAt: "2026-04-11T08:00:00Z",
    summary:
      "Transformer architectures have become the dominant paradigm in NLP since the introduction of the attention mechanism. Multiple studies confirm their superiority over RNN-based approaches for most sequence tasks. Pre-training strategies like those introduced by BERT have further extended the capabilities of these models across diverse benchmarks.",
    agreements: [
      "Attention mechanisms outperform recurrence for long-range dependencies [1][3]",
      "Pre-training on large corpora followed by fine-tuning is highly effective [2]",
      "Transformers enable better parallelization during training than RNNs [1]",
    ],
    contradictions: [
      "Paper [1] claims transformers require more data than RNNs, while [2] shows competitive performance with less data using pre-training.",
    ],
    researchGaps: [
      "No comprehensive study on transformer efficiency in low-resource languages.",
      "Longitudinal studies on model degradation over time are lacking.",
      "Hybrid architectures combining attention and recurrence remain underexplored.",
    ],
    citations: [
      {
        index: 1,
        title: "Attention Is All You Need",
        authors: ["Vaswani", "Shazeer"],
        year: 2017,
        source: "local",
        doi: "10.48550/arXiv.1706.03762",
      },
      {
        index: 2,
        title:
          "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        authors: ["Devlin", "Chang"],
        year: 2018,
        source: "local",
        doi: "10.48550/arXiv.1810.04805",
      },
      {
        index: 3,
        title: "Language Models are Few-Shot Learners",
        authors: ["Brown", "Mann"],
        year: 2020,
        source: "external",
        url: "https://arxiv.org/abs/2005.14165",
      },
    ],
    externalPapersFetched: true,
    newPapersCount: 1,
  },
  {
    id: "q2",
    question:
      "Compare transformer architectures with RNN-based language models",
    createdAt: "2026-04-10T15:30:00Z",
    summary:
      "Comparative analysis reveals that transformer models consistently outperform RNN-based models on benchmark tasks while offering better parallelization during training.",
    agreements: [
      "Transformers parallelize better than RNNs during training [1]",
      "Attention allows direct modeling of long-range dependencies [1]",
    ],
    contradictions: [
      "RNNs may still be preferred for streaming/online inference in resource-constrained environments [1][2]",
    ],
    researchGaps: [
      "Hybrid architectures combining attention and recurrence remain underexplored.",
    ],
    citations: [
      {
        index: 1,
        title: "Attention Is All You Need",
        authors: ["Vaswani", "Shazeer"],
        year: 2017,
        source: "local",
      },
      {
        index: 2,
        title: "Chain-of-Thought Prompting",
        authors: ["Wei", "Wang"],
        year: 2022,
        source: "local",
      },
    ],
    externalPapersFetched: false,
    newPapersCount: 0,
  },
  {
    id: "q3",
    question: "Survey of RAG methods in question answering systems",
    createdAt: "2026-04-08T11:45:00Z",
    summary:
      "Retrieval-Augmented Generation (RAG) methods have emerged as a powerful approach to grounding language model outputs in factual sources, significantly reducing hallucination rates.",
    agreements: [
      "RAG reduces hallucination compared to pure generative approaches",
      "Dense retrieval outperforms sparse BM25 for semantic similarity tasks",
    ],
    contradictions: [
      "Some studies show BM25 remains competitive for domain-specific corpora",
    ],
    researchGaps: ["Real-time RAG for streaming applications is under-studied"],
    citations: [
      {
        index: 1,
        title: "Retrieval-Augmented Generation for Knowledge-Intensive NLP",
        authors: ["Lewis", "Perez"],
        year: 2020,
        source: "external",
        url: "https://arxiv.org/abs/2005.11401",
      },
    ],
    externalPapersFetched: true,
    newPapersCount: 1,
  },
];

export const MOCK_DB_STATS: DbStats = {
  paperCount: 47,
  dbSizeMB: 128,
  isConnected: true,
};
