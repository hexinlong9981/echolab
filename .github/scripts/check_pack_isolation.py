"""ドメインパックの変更がコアを変えていないことを、git の履歴で検査する（ADR-0003・ADR-0009）。

規則:

1. 1 つのコミットで ``domains/`` と ``core/`` の両方を変えない。
   コアを広げる必要があるときは、ドメインに依存しない変更として別のコミットにする。
   検査するのは ``--base`` から ``--head`` までのコミット（push・pull request で増えた分）。
2. 各パックの ``domain.yaml`` を追加したコミットは ``core/`` を変えていない。
   コアと一緒に作った最初のパック（``FOUNDING_PACKS``）は除く。履歴の全体を見る。

使い方::

    python .github/scripts/check_pack_isolation.py --base <SHA> --head <SHA>

``--base`` が空・すべて 0（新しいブランチの最初の push）・履歴に無いときは、``--head`` の
コミットだけを規則 1 で検査する。違反があれば理由を表示して終了コード 1 で終える。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

#: コアと同時に作った最初のパック。規則 2 の対象外。
FOUNDING_PACKS = frozenset({"wuwa"})


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def changed_files(commit: str, *, cwd: Path) -> list[str]:
    out = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit, cwd=cwd)
    return [line for line in out.splitlines() if line]


def touches(files: list[str], top: str) -> bool:
    return any(f.startswith(f"{top}/") for f in files)


def commits_in_range(base: str | None, head: str, *, cwd: Path) -> list[str]:
    if base and set(base) != {"0"}:
        try:
            git("cat-file", "-e", f"{base}^{{commit}}", cwd=cwd)
            return git("rev-list", f"{base}..{head}", cwd=cwd).split()
        except subprocess.CalledProcessError:
            pass
    return [git("rev-parse", head, cwd=cwd).strip()]


def mixed_commits(commits: list[str], *, cwd: Path) -> list[str]:
    """規則 1 の違反：``domains/`` と ``core/`` を同時に変えたコミット。"""
    bad = []
    for commit in commits:
        files = changed_files(commit, cwd=cwd)
        if touches(files, "domains") and touches(files, "core"):
            bad.append(commit)
    return bad


def packs_added_with_core_changes(head: str, *, cwd: Path) -> list[tuple[str, str]]:
    """規則 2 の違反：(パック名, パックを追加したコミット) の列。"""
    bad = []
    tree = git("ls-tree", "--name-only", f"{head}:domains", cwd=cwd).split()
    for pack in sorted(tree):
        if pack in FOUNDING_PACKS:
            continue
        manifest = f"domains/{pack}/domain.yaml"
        added = git("log", "--diff-filter=A", "--format=%H", head, "--", manifest, cwd=cwd).split()
        for commit in added:
            if touches(changed_files(commit, cwd=cwd), "core"):
                bad.append((pack, commit))
    return bad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ドメインパックの変更がコアを変えていないか検査する")
    p.add_argument("--base", default="", help="検査する範囲の起点（このコミットは含まない）")
    p.add_argument("--head", default="HEAD", help="検査する範囲の終点")
    p.add_argument("--repo", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    commits = commits_in_range(args.base or None, args.head, cwd=args.repo)
    problems = [
        f"{c[:12]}: 1 つのコミットで domains/ と core/ の両方を変えています。"
        "コアの変更は、ドメインに依存しない別のコミットにしてください"
        for c in mixed_commits(commits, cwd=args.repo)
    ]
    problems += [
        f"{c[:12]}: パック {pack} を追加したコミットが core/ を変えています"
        for pack, c in packs_added_with_core_changes(args.head, cwd=args.repo)
    ]
    for problem in problems:
        print(f"エラー: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"OK: {len(commits)} 件のコミットと、すべてのパックの追加でコアの差分はありません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
