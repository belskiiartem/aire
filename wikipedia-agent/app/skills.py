"""Minimal Agent Skills (agentskills.io) runtime: discovery, progressive disclosure, sandboxed script runs."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass
class Skill:
    name: str
    description: str
    path: Path

    @property
    def body(self) -> str:
        text = (self.path / "SKILL.md").read_text(encoding="utf-8")
        return text.split("---", 2)[2].strip() if text.startswith("---") else text


def _parse(skill_md: Path) -> Skill:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{skill_md}: missing YAML frontmatter")
    meta = yaml.safe_load(text.split("---", 2)[1]) or {}
    name, desc = meta.get("name", ""), meta.get("description", "")
    if not NAME_RE.match(name) or name != skill_md.parent.name:
        raise ValueError(f"{skill_md}: name {name!r} must be kebab-case and match the directory")
    if not desc or len(desc) > 1024:
        raise ValueError(f"{skill_md}: description must be 1-1024 characters")
    return Skill(name, desc.strip(), skill_md.parent)


class SkillRegistry:
    def __init__(self, root: Path):
        self.skills = {s.name: s for s in (_parse(p) for p in sorted(root.glob("*/SKILL.md")))}

    def get(self, name: str) -> Skill:
        if name not in self.skills:
            raise KeyError(f"unknown skill {name!r}; available: {', '.join(self.skills) or 'none'}")
        return self.skills[name]

    def catalogue(self) -> str:
        return "\n".join(f"- {s.name}: {s.description}" for s in self.skills.values())

    def read_file(self, name: str, rel: str) -> str:
        skill = self.get(name)
        target = (skill.path / rel).resolve()
        if skill.path.resolve() not in target.parents or not target.is_file():
            raise ValueError(f"{rel!r} is not a file inside skill {name}")
        return target.read_text(encoding="utf-8")

    def run_command(self, name: str, command: str, env: dict[str, str], timeout: int, limit: int) -> str:
        """Run a command line exactly as written in SKILL.md, e.g. `python scripts/x analyze --flag "a b"`.

        Parsed with shlex and executed without a shell; only files in the skill's scripts/ may run.
        """
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            raise ValueError(f"cannot parse command: {exc}") from exc
        while argv and re.fullmatch(r"python[0-9.]*|uv|run", argv[0]):
            argv = argv[1:]
        if not argv:
            raise ValueError("empty command")
        return self.run_script(name, argv[0].removeprefix("./").removeprefix("scripts/"), argv[1:], env, timeout, limit)

    def run_script(self, name: str, script: str, args: list[str], env: dict[str, str],
                   timeout: int, limit: int) -> str:
        """Run scripts/<script> with the agent's Python. No shell, argv only, cwd = skill dir."""
        skill = self.get(name)
        scripts = (skill.path / "scripts").resolve()
        target = (scripts / script).resolve()
        if target.parent != scripts or not target.is_file():
            available = sorted(p.name for p in scripts.iterdir() if p.is_file())
            raise ValueError(f"script {script!r} not found; available: {available}")
        proc = subprocess.run([sys.executable, str(target), *map(str, args)], cwd=skill.path,
                              env={**os.environ, **env}, capture_output=True, text=True, timeout=timeout)
        out = proc.stdout.strip()
        if proc.returncode != 0:
            # argparse errors and tracebacks: keep the tail, that is where the useful line is
            out = f"exit code {proc.returncode}\n{out}\n{proc.stderr.strip()[-3000:]}"
        return out if len(out) <= limit else out[:limit] + f"\n... [truncated {len(out) - limit} chars]"
