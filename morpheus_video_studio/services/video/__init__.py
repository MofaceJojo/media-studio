# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Video processing package.

Split from the former 1800-line video.py into concern modules:
probe / motion / concat / segments / bgm, composed by the VideoService facade.
Import surface is unchanged: `from morpheus_video_studio.services.video import VideoService`.
"""

from morpheus_video_studio.services.video.service import VideoService
from morpheus_video_studio.services.video.probe import check_ffmpeg
from morpheus_video_studio.services.video.concat import XFADES

__all__ = ["VideoService", "check_ffmpeg", "XFADES"]
