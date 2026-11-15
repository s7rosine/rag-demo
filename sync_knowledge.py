"""Manual, least-privilege sync runner for scoped cloud knowledge sources.

Run with --apply in an approved cloud worker. Never invoke from a public route
or on every serverless request. Source deletion reconciliation is NOT included.
"""
import argparse
import hashlib
import os

from cloud_sources import configured_documents
from platform_core import Repository, Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync approved cloud documents into RAG")
    parser.add_argument("--source", choices=["s3", "notion", "gdrive"], required=True)
    parser.add_argument("--kb", default="default")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--apply", action="store_true",
                        help="Actually fetch/index documents; omitted means config-only preview")
    args = parser.parse_args()
    if not 1 <= args.limit <= 500 or not args.kb.replace("-", "").replace("_", "").isalnum():
        parser.error("Invalid knowledge-base name or limit")
    org = os.getenv("RAG_ORG", "")
    if not org:
        parser.error("RAG_ORG is required")
    if not args.apply:
        print("Dry run: source=" + args.source + ", kb=" + args.kb
              + ", limit=" + str(args.limit) + ". Use --apply to ingest.")
        return
    settings = Settings()
    settings.ensure_writable()
    repo = Repository(settings)
    total = 0
    skipped = 0
    for doc in configured_documents(args.source, args.limit):
        # Source IDs are stable (S3 key, Notion page, Drive file ID).
        # Prefix the source ID so equal filenames across systems do not clash.
        content_hash = hashlib.sha256(doc.data).hexdigest()
        if repo.has_document(org, args.kb, doc.source, content_hash):
            skipped += 1
            continue
        result = repo.ingest(org, args.kb, doc.source, doc.data)
        total += 1
        print("Indexed " + doc.source + " (" + str(result["chunks_indexed"]) + " chunks)")
    print("Complete: indexed=" + str(total) + ", unchanged=" + str(skipped))


if __name__ == "__main__":
    main()
