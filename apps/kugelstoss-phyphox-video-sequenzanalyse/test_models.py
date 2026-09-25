from __future__ import annotations

import unittest

from signals import ProcessingSettings, detect_phases, enrich_signals, make_demo_frame
from video_sequences import phase_bounds, synchronization_from_anchors, video_frame_to_sensor_time


class SequenceTests(unittest.TestCase):
    def test_phase_bounds(self) -> None:
        events = {"Bewegungsbeginn": 100, "Release": 300, "Abfangen": 360}
        self.assertEqual(phase_bounds(events, "Release", 500), (300, 360))

    def test_two_anchor_sync(self) -> None:
        slope, offset = synchronization_from_anchors(100, 1.0, 300, 2.0)
        self.assertAlmostEqual(video_frame_to_sensor_time(200, slope, offset), 1.5)


class SignalTests(unittest.TestCase):
    def test_demo_detection(self) -> None:
        enriched, rate = enrich_signals(make_demo_frame(), ProcessingSettings())
        events = detect_phases(enriched, rate)
        labels = {event.label for event in events}
        self.assertIn("Bewegungsbeginn", labels)
        self.assertIn("Release", labels)
        self.assertGreater(rate, 100.0)


if __name__ == "__main__":
    unittest.main()
