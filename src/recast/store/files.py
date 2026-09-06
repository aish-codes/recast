"""Local-filesystem backend: one directory per application.

This is what the CLI uses, and it is deliberately the default. Plain files mean
you can open, diff and version your own applications with ordinary tools, and it
needs no service running to try the thing out.
"""

from __future__ import annotations

from pathlib import Path

from ..models.analysis import Analysis
from ..models.job import JobDescription
from ..models.profile import MasterProfile
from ..models.tailored import CoverLetter, TailoredResume
from .base import Application


class FileStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def app_dir(self, job_id: str) -> Path:
        d = self.root / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _write(self, job_id: str, name: str, model) -> None:
        (self.app_dir(job_id) / name).write_text(model.model_dump_json(indent=2), encoding="utf-8")

    def _read(self, job_id: str, name: str, cls):
        path = self.app_dir(job_id) / name
        if not path.exists():
            raise KeyError(f"{name} missing for {job_id}")
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save_job(self, jd: JobDescription, user: str = "") -> None:
        self._write(jd.id, "job.json", jd)

    def load_job(self, job_id: str, user: str = "") -> JobDescription:
        return self._read(job_id, "job.json", JobDescription)

    def save_resume(self, resume: TailoredResume, user: str = "") -> None:
        self._write(resume.job_id, "resume.json", resume)

    def load_resume(self, job_id: str, user: str = "") -> TailoredResume:
        return self._read(job_id, "resume.json", TailoredResume)

    def save_cover_letter(self, letter: CoverLetter, user: str = "") -> None:
        self._write(letter.job_id, "cover_letter.json", letter)
        (self.app_dir(letter.job_id) / "cover_letter.txt").write_text(letter.text(), "utf-8")

    def load_cover_letter(self, job_id: str, user: str = "") -> CoverLetter:
        return self._read(job_id, "cover_letter.json", CoverLetter)

    def save_application(self, app: Application, user: str = "") -> None:
        self._write(app.job_id, "app.json", app.touch())

    def load_application(self, job_id: str, user: str = "") -> Application:
        try:
            return self._read(job_id, "app.json", Application)
        except KeyError:
            return Application(job_id=job_id)

    def list_applications(self, user: str = "") -> list[Application]:
        if not self.root.exists():
            return []
        apps = []
        for d in sorted(self.root.iterdir()):
            f = d / "app.json"
            if f.is_file():
                apps.append(Application.model_validate_json(f.read_text(encoding="utf-8")))
        return sorted(apps, key=lambda a: a.updated, reverse=True)

    def delete_application(self, job_id: str, user: str = "") -> None:
        import shutil

        shutil.rmtree(self.root / job_id, ignore_errors=True)

    def save_analysis(self, analysis: Analysis, user: str = "") -> None:
        self._write(analysis.job_id, "analysis.json", analysis)

    def load_analysis(self, analysis_id: str, user: str = "") -> Analysis:
        # Locally there is one analysis per application directory, so the id is
        # only checked, not used to address it.
        for d in sorted(self.root.iterdir()) if self.root.exists() else []:
            path = d / "analysis.json"
            if path.is_file():
                a = Analysis.model_validate_json(path.read_text(encoding="utf-8"))
                if a.id == analysis_id:
                    return a
        raise KeyError(f"no analysis {analysis_id}")

    def find_analysis(
        self, fingerprint: str, job_id: str, ruleset: str, user: str = ""
    ) -> Analysis | None:
        path = self.root / job_id / "analysis.json"
        if not path.is_file():
            return None
        a = Analysis.model_validate_json(path.read_text(encoding="utf-8"))
        matches = (a.resume_fingerprint == fingerprint and a.ruleset_version == ruleset)
        return a if matches else None

    # The profile lives at a path the user chooses, so these take one explicitly.
    def save_profile(self, profile: MasterProfile, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(profile.model_dump_json(indent=2), encoding="utf-8")

    def load_profile(self, path: Path) -> MasterProfile:
        return MasterProfile.model_validate_json(Path(path).read_text(encoding="utf-8"))
