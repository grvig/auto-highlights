"""Encoder settings for the editor's in-between files.

Each edited part is encoded once more before the reel is exported, so the
intermediate steps favour speed with a little extra quality headroom; only
the final export spends time on compression.
"""

INTERMEDIATE_VIDEO = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p"]
