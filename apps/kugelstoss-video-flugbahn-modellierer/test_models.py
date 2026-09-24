from __future__ import annotations

import math
import unittest

import numpy as np

from trajectory import TrajectoryParameters, simulate
from video_analysis import Calibration, estimate_slow_factor, fit_release_parameters, pixel_to_world, world_to_pixel


class VideoAnalysisTests(unittest.TestCase):
    def test_slow_factor(self) -> None:
        self.assertAlmostEqual(estimate_slow_factor(10, 70, 100, 340), 4.0)

    def test_affine_calibration(self) -> None:
        calibration = Calibration(
            origin_px=(100.0, 500.0),
            x_reference_px=(500.0, 500.0),
            x_distance_m=2.0,
            z_reference_px=(100.0, 100.0),
            z_distance_m=2.0,
        )
        x_m, z_m = pixel_to_world((300.0, 300.0), calibration)
        self.assertAlmostEqual(x_m, 1.0)
        self.assertAlmostEqual(z_m, 1.0)

    def test_negative_x_reference_keeps_throwing_direction_positive(self) -> None:
        calibration = Calibration(
            origin_px=(500.0, 500.0),
            x_reference_px=(100.0, 500.0),
            x_distance_m=-2.0,
            z_reference_px=(500.0, 100.0),
            z_distance_m=2.0,
        )
        x_ref_m, x_ref_z_m = pixel_to_world((100.0, 500.0), calibration)
        forward_x_m, forward_z_m = pixel_to_world((700.0, 300.0), calibration)
        self.assertAlmostEqual(x_ref_m, -2.0)
        self.assertAlmostEqual(x_ref_z_m, 0.0)
        self.assertAlmostEqual(forward_x_m, 1.0)
        self.assertAlmostEqual(forward_z_m, 1.0)

    def test_z_reference_can_be_above_x_reference(self) -> None:
        calibration = Calibration(
            origin_px=(100.0, 500.0),
            x_reference_px=(500.0, 500.0),
            x_distance_m=2.0,
            z_reference_px=(500.0, 100.0),
            z_distance_m=2.0,
            z_reference_x_m=2.0,
        )
        x_m, z_m = pixel_to_world((300.0, 300.0), calibration)
        z_ref_x_m, z_ref_z_m = pixel_to_world((500.0, 100.0), calibration)
        self.assertAlmostEqual(x_m, 1.0)
        self.assertAlmostEqual(z_m, 1.0)
        self.assertAlmostEqual(z_ref_x_m, 2.0)
        self.assertAlmostEqual(z_ref_z_m, 2.0)

    def test_world_to_pixel_is_inverse_for_offset_z_reference(self) -> None:
        calibration = Calibration(
            origin_px=(140.0, 520.0),
            x_reference_px=(540.0, 500.0),
            x_distance_m=2.0,
            z_reference_px=(500.0, 120.0),
            z_distance_m=2.0,
            z_reference_x_m=2.0,
        )
        expected_world = (2.75, 1.65)
        pixel = world_to_pixel(expected_world, calibration)
        actual_world = pixel_to_world(pixel, calibration)
        self.assertAlmostEqual(actual_world[0], expected_world[0])
        self.assertAlmostEqual(actual_world[1], expected_world[1])

    def test_release_fit_recovers_synthetic_parameters(self) -> None:
        calibration = Calibration(
            origin_px=(100.0, 600.0),
            x_reference_px=(300.0, 600.0),
            x_distance_m=1.0,
            z_reference_px=(100.0, 400.0),
            z_distance_m=1.0,
        )
        fps = 60.0
        slow_factor = 4.0
        release_frame = 200
        vx = 8.2
        vz = 6.1
        x0 = 0.45
        h0 = 1.85
        points: dict[int, tuple[float, float]] = {}
        for frame in range(release_frame, release_frame + 31, 5):
            t = (frame - release_frame) / (fps * slow_factor)
            x = x0 + vx * t
            z = h0 + vz * t - 0.5 * 9.81 * t**2
            points[frame] = (100.0 + 200.0 * x, 600.0 - 200.0 * z)

        fit, measured = fit_release_parameters(
            points,
            calibration,
            fps=fps,
            slow_factor=slow_factor,
            release_frame=release_frame,
        )
        self.assertAlmostEqual(fit.vx_m_s, vx, places=8)
        self.assertAlmostEqual(fit.vz_m_s, vz, places=8)
        self.assertAlmostEqual(fit.release_x_m, x0, places=8)
        self.assertAlmostEqual(fit.release_height_m, h0, places=8)
        self.assertLess(fit.rmse_m, 1e-10)
        self.assertEqual(len(measured), len(points))

    def test_release_fit_is_anchored_to_clicked_release_marker(self) -> None:
        calibration = Calibration(
            origin_px=(0.0, 400.0),
            x_reference_px=(200.0, 400.0),
            x_distance_m=1.0,
            z_reference_px=(0.0, 200.0),
            z_distance_m=1.0,
        )
        release_frame = 100
        points = {
            release_frame: (100.0, 40.0),
            release_frame + 5: (180.0, 4.0),
            release_frame + 10: (265.0, -18.0),
            release_frame + 15: (338.0, -30.0),
        }
        fit, _ = fit_release_parameters(
            points,
            calibration,
            fps=100.0,
            slow_factor=1.0,
            release_frame=release_frame,
        )
        release_x_m, release_z_m = pixel_to_world(points[release_frame], calibration)
        self.assertAlmostEqual(fit.release_x_m, release_x_m)
        self.assertAlmostEqual(fit.release_height_m, release_z_m)


class TrajectoryTests(unittest.TestCase):
    def test_simulation_lands_on_ground(self) -> None:
        result = simulate(TrajectoryParameters("Test", 10.0, 37.0, 1.8))
        self.assertAlmostEqual(float(result.data.iloc[-1]["z_m"]), 0.0)
        self.assertGreater(result.flight_distance_m, 0.0)
        self.assertTrue(math.isfinite(result.peak_height_m))


if __name__ == "__main__":
    unittest.main()
