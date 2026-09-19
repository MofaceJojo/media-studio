"""Grounded bilingual facts and deterministic visual prompts for one narration."""

from dataclasses import dataclass, field

from morpheus_video_studio.utils.visual_prompt_policy import sanitize_visual_prompt


@dataclass
class VisualFact:
    """A source excerpt and its English translation for a single visual fact."""

    source: str = ""
    english: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not isinstance(self.english, str):
            raise ValueError("fact source and english must be strings")
        self.source = self.source.strip()
        self.english = self.english.strip()
        if bool(self.source) != bool(self.english):
            raise ValueError("fact source and english must be paired")

    @property
    def is_blank(self) -> bool:
        return not self.source


@dataclass
class VisualScenePlan:
    subject: VisualFact
    location: VisualFact = field(default_factory=VisualFact)
    action: VisualFact = field(default_factory=VisualFact)
    outcome: VisualFact = field(default_factory=VisualFact)
    evidence: VisualFact = field(default_factory=VisualFact)
    image_prompt: str = field(init=False, default="")
    video_prompt: str = field(init=False, default="")

    def __post_init__(self) -> None:
        for field_name in ("subject", "location", "action", "outcome", "evidence"):
            if not isinstance(getattr(self, field_name), VisualFact):
                raise ValueError(f"{field_name} must be a VisualFact")
        if self.subject.is_blank:
            raise ValueError("subject fact must not be blank")

    def validate_narration_facts(self, narration: str) -> None:
        """Require each non-blank source excerpt to be copied from narration."""
        if not isinstance(narration, str) or not narration.strip():
            raise ValueError("narration must be a non-blank string")
        for field_name in ("subject", "location", "action", "outcome", "evidence"):
            fact = getattr(self, field_name)
            if not fact.is_blank and fact.source not in narration:
                raise ValueError(f"{field_name} source must be copied from narration")

    def build_prompts(self) -> None:
        """Build both safe English prompts from fact translations and fixed clauses."""
        facts = [
            getattr(self, field_name).english
            for field_name in ("subject", "location", "action", "outcome", "evidence")
            if not getattr(self, field_name).is_blank
        ]
        composition = [
            "grounded reference imagery",
            "natural documentary style",
            "distant back-view silhouette",
            "face fully turned away",
            "hands outside the frame",
        ]
        self.image_prompt = sanitize_visual_prompt(
            ", ".join([*facts, *composition])
        )
        self.video_prompt = sanitize_visual_prompt(
            ", ".join([*facts, *composition, "slow camera movement"])
        )
