# LegacyLens

## Building RAG Systems for Legacy Enterprise Codebases

## Before You Start: Pre-Search (60 Minutes)

Before writing any code, complete the Pre-Search methodology at the end of this document.
This structured process uses AI to explore vector database options, embedding strategies, and RAG architecture decisions.
Your Pre-Search output becomes part of your final submission.

This week emphasizes RAG architecture selection and implementation.
Pre-Search helps you choose the right vector database and retrieval strategy for your use case.

## Background

Enterprise systems running on COBOL, Fortran, and other legacy languages power critical infrastructure: banking transactions, insurance claims, government services, and scientific computing.
These codebases contain decades of business logic, but few engineers understand them.

This project requires you to build a RAG-powered system that makes large legacy codebases queryable and understandable.
You will work with real open source enterprise projects, implementing retrieval pipelines that help developers navigate unfamiliar code through natural language.

The focus is on RAG architecture: vector databases, embedding strategies, chunking approaches, and retrieval pipelines that actually work on complex codebases.

**Gate:** Behavioral and technical interviews required for Austin admission.

## Project Overview

One-week sprint with three deadlines:

| Checkpoint | Deadline | Focus |
| --- | --- | --- |
| MVP | Tuesday (24 hours) | Basic RAG pipeline working |
| Final (G4) | Wednesday (3 days) | Polish, documentation, deployment |
| Final (GFA) | Sunday (5 days) | Polish, documentation, deployment |

## MVP Requirements (24 Hours)

Hard gate. All items required to pass:

- [ ] Ingest at least one legacy codebase (COBOL, Fortran, or similar)
- [ ] Chunk code files with syntax-aware splitting
- [ ] Generate embeddings for all chunks
- [ ] Store embeddings in a vector database
- [ ] Implement semantic search across the codebase
- [ ] Natural language query interface (CLI or web)
- [ ] Return relevant code snippets with file/line references
- [ ] Basic answer generation using retrieved context
- [ ] Deployed and publicly accessible

A simple RAG pipeline with accurate retrieval beats a complex system with irrelevant results.

## Target Codebases

Choose **ONE** primary codebase from this list (or propose an alternative of similar scope):

| Project | Language | Description |
| --- | --- | --- |
| GnuCOBOL | COBOL | Open source COBOL compiler |
| GNU Fortran (gfortran) | Fortran | Fortran compiler in GCC |
| LAPACK | Fortran | Linear algebra library |
| BLAS | Fortran | Basic linear algebra subprograms |
| OpenCOBOL Contrib | COBOL | Sample COBOL programs and utilities |
| Custom proposal | Any legacy | Get approval before starting |

Minimum codebase size: **10,000+ lines of code across 50+ files**.

## Core RAG Infrastructure

### Ingestion Pipeline

| Component | Requirements |
| --- | --- |
| File Discovery | Recursively scan codebase, filter by file extension |
| Preprocessing | Handle encoding issues, normalize whitespace, extract comments |
| Chunking | Syntax-aware splitting (functions, paragraphs, sections) |
| Metadata Extraction | File path, line numbers, function names, dependencies |
| Embedding Generation | Generate vectors for each chunk with chosen model |
| Storage | Insert into vector database with metadata |

### Retrieval Pipeline

| Component | Requirements |
| --- | --- |
| Query Processing | Parse natural language, extract intent and entities |
| Embedding | Convert query to vector using same model as ingestion |
| Similarity Search | Find top-k most similar chunks |
| Re-ranking | Optional: reorder results by relevance score |
| Context Assembly | Combine retrieved chunks with surrounding context |
| Answer Generation | LLM generates response using retrieved context |

## Chunking Strategies

Legacy code requires specialized chunking. Document your approach:

| Strategy | Use Case |
| --- | --- |
| Function-level | Each function/subroutine as a chunk |
| Paragraph-level (COBOL) | COBOL PARAGRAPH as natural boundary |
| Fixed-size + overlap | Fallback for unstructured sections |

## LegacyLens Implementation Status (March 2, 2026)

### MVP Gate Checklist

- [x] Ingest at least one legacy codebase
- [x] Chunk code files with syntax-aware splitting
- [x] Generate embeddings for all chunks
- [x] Store embeddings in a vector database
- [x] Implement semantic search across the codebase
- [x] Natural language query interface (CLI and web API)
- [x] Return relevant code snippets with file/line references
- [x] Basic answer generation using retrieved context
- [x] Deployed and publicly accessible

### Full Presearch Differentiators

- [x] Deterministic tag assignment (`io`, `error_handling`, `entry_candidate`)
- [x] Parser health check warning when fallback chunks exceed 30%
- [x] Query embedding cache (in-process LRU)
- [x] PERFORM/CALL dependency graph generation at ingestion
- [x] Dependency lookup interface (`callers` CLI and `/callers/{symbol}` API)
- [x] Precision@5 evaluation harness with per-query logging

### Public Endpoints

- API root: `https://legacylens-api-production.up.railway.app/`
- Health: `https://legacylens-api-production.up.railway.app/health`
- Query: `POST https://legacylens-api-production.up.railway.app/query`
