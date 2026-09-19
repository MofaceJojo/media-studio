# API Usage

Morpheus Video Studio provides a complete Python API for easy integration into your projects.

---

## Quick Start

```python
from morpheus_video_studio.service import MorpheusVideoStudioCore
import asyncio

async def main():
    # Initialize
    morpheus = MorpheusVideoStudioCore()
    await morpheus.initialize()
    
    # Generate video
    result = await morpheus.generate_video(
        text="Why develop a reading habit",
        mode="generate",
        n_scenes=5
    )
    
    print(f"Video generated: {result.video_path}")

# Run
asyncio.run(main())
```

---

## API Reference

For detailed API documentation, see [API Overview](../reference/api-overview.md).

---

## Examples

For more usage examples, check the `examples/` directory in the project.

