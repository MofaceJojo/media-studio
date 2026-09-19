from dataclasses import dataclass


@dataclass
class SceneDraft:
    index: int
    narration: str
    image_prompt: str = ""
    video_prompt: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "narration": self.narration,
            "image_prompt": self.image_prompt,
            "video_prompt": self.video_prompt,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SceneDraft":
        narration = value.get("narration")
        image_prompt = value.get("image_prompt")
        video_prompt = value.get("video_prompt")
        return cls(
            index=int(value["index"]),
            narration="" if narration is None else str(narration),
            image_prompt="" if image_prompt is None else str(image_prompt),
            video_prompt="" if video_prompt is None else str(video_prompt),
        )
