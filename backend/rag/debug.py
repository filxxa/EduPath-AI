"""CLI helper for inspecting the RAG pipeline end-to-end.

Usage:
    python -m backend.rag.debug "Am I eligible for NUST?"
    python -m backend.rag.debug --build
    python -m backend.rag.debug --check

Pass --build to synthesize policy files and rebuild the ChromaDB index.
Pass --check to verify that the Groq API key is configured.
Otherwise, pass a question and the tool prints retrieved chunks, the
assembled prompt, the generated answer, and source labels.
"""
from __future__ import annotations

import argparse
import sys

from backend.rag import ask, build_index, is_available
from backend.rag.config import POLICIES_DIR, UNIVERSITIES_PATH
from backend.rag.indexer import build_collection, get_persistent_client, index_policies
from backend.rag.prompter import build_prompt
from backend.rag.retriever import get_retriever


def cmd_check() -> int:
    print(f"Groq API key configured: {is_available()}")
    print(f"Policy corpus directory: {POLICIES_DIR}")
    if POLICIES_DIR.exists():
        txt_files = list(POLICIES_DIR.glob("**/*.txt"))
        print(f"Policy text files on disk: {len(txt_files)}")
    else:
        print("Policy corpus directory does not exist. Run --build first.")

    try:
        client = get_persistent_client()
        collection = build_collection(client)
        print(f"ChromaDB collection '{collection.name}' count: {collection.count()}")
    except Exception as exc:
        print(f"ChromaDB error: {exc}")
    return 0


def cmd_build() -> int:
    print("Synthesizing policy files and building index...")
    result = build_index(force=True)
    if result.error:
        print(f"Build failed: {result.error}")
        return 1
    print(
        f"Synthesized {result.synthesized_files} files, "
        f"indexed {result.indexed_chunks} chunks ({result.new_chunks} new)."
    )
    return 0


def cmd_ask(question: str) -> int:
    if not is_available():
        print("Warning: Groq API key not configured. Falling back to rule-based advisor.\n")

    retriever = get_retriever()
    evidence = retriever.retrieve(question)

    print("Retrieved chunks:")
    for index, chunk in enumerate(evidence, start=1):
        print(f"  [{index}] {chunk.source_label} (distance={chunk.distance:.4f})")
        for line in chunk.text.splitlines()[:3]:
            print(f"      {line}")
        print()

    bundle = build_prompt(question=question, evidence=evidence, profile=None, eligibility=None)
    print("System prompt:")
    print(bundle.system)
    print("\nUser message:")
    print(bundle.user_message)
    print("\n" + "=" * 60 + "\n")

    result = ask(question)
    print(f"Engine: {result.engine}")
    if result.error:
        print(f"Error: {result.error}")
    print("\nAnswer:")
    print(result.answer)
    if result.sources:
        print("\nSources:")
        for source in result.sources:
            print(f"  - {source}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EduPath AI RAG debug helper")
    parser.add_argument("question", nargs="?", help="Student question to ask")
    parser.add_argument("--build", action="store_true", help="Rebuild the policy index")
    parser.add_argument("--check", action="store_true", help="Check pipeline configuration")
    args = parser.parse_args()

    if args.check:
        return cmd_check()
    if args.build:
        return cmd_build()
    if args.question:
        return cmd_ask(args.question)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
