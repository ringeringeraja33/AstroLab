import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "astrolab" / "scripts" / "astro_calc.py"
SPEC = importlib.util.spec_from_file_location("astro_calc", SCRIPT)
astro = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(astro)


class AstroCalcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.chart_path = Path(cls.tempdir.name) / "sample.chart.json"
        args = SimpleNamespace(
            date="1990-05-15", time="14:30", tz=8.0,
            tz_name=None, fold=None, lat=39.9, lon=116.4, hsys="P",
            engine="auto", ephe_path=None, jpl_file=None, bodies=None,
        )
        chart = astro.compute_natal(args)
        cls.chart_path.write_text(json.dumps(chart), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def capture(self, func, **kwargs):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            func(SimpleNamespace(**kwargs))
        return stream.getvalue()

    def test_fractional_timezone_formatting(self):
        self.assertEqual(astro.fmt_tz(5.5), "+05:30")
        self.assertEqual(astro.fmt_tz(5.75), "+05:45")
        self.assertEqual(astro.fmt_tz(-3.5), "-03:30")

    def test_name_lists_are_deduplicated_in_input_order(self):
        self.assertEqual(
            astro.parse_names("saturn,saturn,mars,saturn", astro.PLANETS, "planet"),
            ["saturn", "mars"],
        )

    def test_invalid_dates_and_reversed_ranges_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid date"):
            astro.jd_from_local("2026-02-30", "12:00", 8)
        with self.assertRaisesRegex(ValueError, "precedes"):
            astro.jd_range("2027-01-01", "2026-01-01", 8)

    def test_polar_placidus_error_suggests_whole_sign_houses(self):
        args = SimpleNamespace(
            date="2026-01-01", time="12:00", tz=0.0,
            lat=80.0, lon=0.0, hsys="P",
        )
        with self.assertRaisesRegex(ValueError, "Try --hsys W"):
            astro.compute_natal(args)

    def test_end_date_is_inclusive(self):
        output = self.capture(
            astro.cmd_lunations,
            natal=str(self.chart_path), start="2026-07-14", end="2026-07-14",
            orb=3.0, tz=None,
        )
        self.assertIn("2026-07-14 17:44", output)

    def test_fast_planet_applying_state_uses_instantaneous_motion(self):
        output = self.capture(
            astro.cmd_snapshot,
            natal=str(self.chart_path), date="2026-07-14", time="17:15",
            tz=None, orb_scale=1.0,
        )
        self.assertRegex(
            output,
            r"Moon\s+opposition\s+natal Moon\s+orb 2\.65°\s+applying",
        )

    def test_pass_numbers_include_hits_outside_query_window(self):
        output = self.capture(
            astro.cmd_transits,
            natal=str(self.chart_path), start="2026-08-01", end="2027-03-01",
            planets="saturn", targets="venus", aspects="conjunction", tz=None,
        )
        self.assertIn("2026-09-18 11:56", output)
        self.assertIn("(pass 2/3)", output)
        self.assertIn("2027-02-24 15:58", output)
        self.assertIn("(pass 3/3)", output)

    def test_five_pass_pluto_series_is_kept_together(self):
        output = self.capture(
            astro.cmd_transits,
            natal=str(self.chart_path), start="2020-01-01", end="2030-12-31",
            planets="pluto", targets="moon", aspects="conjunction", tz=None,
            quiet=True,
        )
        for number in range(1, 6):
            self.assertIn(f"(pass {number}/5)", output)

    def test_tangent_zero_is_detected_without_sign_change(self):
        hits = astro.scan_crossings(lambda value: (value - 1.13) ** 2, 0, 2, 0.25)
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0], 1.13, places=5)

    def test_chart_validation_rejects_bad_nested_values(self):
        chart = json.loads(self.chart_path.read_text(encoding="utf-8"))
        chart["meta"]["tz"] = "bad"
        broken = Path(self.tempdir.name) / "broken.chart.json"
        broken.write_text(json.dumps(chart), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "UTC offset"):
            astro.load_chart(broken)

        chart["meta"]["tz"] = 8.0
        chart["points"]["sun"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            astro.validate_chart(chart)

    def test_chart_records_engine_and_extended_coordinates_without_private_path(self):
        chart = astro.load_chart(self.chart_path)
        self.assertEqual(chart["schema_version"], 2)
        self.assertIn("true_node", chart["coordinates"])
        self.assertIn("lilith", chart["coordinates"])
        self.assertIn("declination", chart["coordinates"]["sun"])
        metadata = chart["meta"]["ephemeris"]
        self.assertIn("actual_engines", metadata)
        self.assertNotIn("ephemeris_path", metadata)
        self.assertNotIn(str(Path.home()), json.dumps(chart))

    def test_strict_swiss_engine_rejects_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(engine="swiss", ephe_path=directory, jpl_file=None)
            astro.configure_ephemeris(args)
            with self.assertRaisesRegex(ValueError, "ephemeris download"):
                astro.lon_of(astro.jd_from_local("2026-07-14", "12:00", 0), astro.PLANETS["sun"])

    def test_ephemeris_download_is_atomic_and_hashed(self):
        class Response(io.BytesIO):
            headers = {"Content-Length": "12"}

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(astro.urllib.request, "urlopen", return_value=Response(b"ephemeris12")):
                record = astro.download_ephemeris_file("sample.se1", Path(directory))
            self.assertEqual((Path(directory) / "sample.se1").read_bytes(), b"ephemeris12")
            self.assertEqual(record["sha256"], "89e6813a8df381b7a0ed54df188146c183d5b0cd5290181b7ee16c3a3cc8b67b")

    def test_legacy_chart_without_schema_version_is_accepted(self):
        chart = json.loads(self.chart_path.read_text(encoding="utf-8"))
        chart.pop("schema_version")
        self.assertIs(astro.validate_chart(chart), chart)

    @unittest.skipIf(os.name == "nt", "POSIX file modes do not apply on Windows")
    def test_chart_save_is_private_and_refuses_overwrite(self):
        chart = astro.load_chart(self.chart_path)
        target = Path(self.tempdir.name) / "private.chart.json"
        astro.save_chart(chart, target)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            astro.save_chart(chart, target)

    def test_iana_timezone_handles_dst_edges(self):
        shanghai = astro.jd_from_zone("2026-07-14", "12:00", "Asia/Shanghai")
        fixed = astro.jd_from_local("2026-07-14", "12:00", 8)
        self.assertAlmostEqual(shanghai, fixed)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            astro.jd_from_zone("2026-03-08", "02:30", "America/New_York")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            astro.jd_from_zone("2026-11-01", "01:30", "America/New_York")
        self.assertNotEqual(
            astro.jd_from_zone("2026-11-01", "01:30", "America/New_York", 0),
            astro.jd_from_zone("2026-11-01", "01:30", "America/New_York", 1),
        )

    def test_station_and_lunation_outputs_are_chronological(self):
        stations = self.capture(
            astro.cmd_stations,
            start="2026-01-01", end="2026-12-31",
            planets="mercury,venus,mars,jupiter,saturn,uranus,neptune,pluto",
            tz=8.0,
        )
        station_dates = [line.strip().split()[0] for line in stations.splitlines()
                         if line.startswith("  20")]
        self.assertEqual(station_dates, sorted(station_dates))

        lunations = self.capture(
            astro.cmd_lunations,
            natal=str(self.chart_path), start="2026-07-01", end="2026-09-30",
            orb=3.0, tz=None,
        )
        lunation_lines = [line for line in lunations.splitlines() if line.startswith("  20")]
        lunation_dates = [line.strip().split()[0] for line in lunation_lines]
        self.assertEqual(lunation_dates, sorted(lunation_dates))
        self.assertIn("New Moon", lunation_lines[0])
        self.assertIn("Full Moon", lunation_lines[1])

    def test_readme_example_is_reproducible(self):
        output = self.capture(
            astro.cmd_transits,
            natal=str(self.chart_path), start="2026-01-01", end="2027-06-30",
            planets="saturn", targets="venus", aspects="conjunction", tz=None,
        )
        self.assertIn("2026-06-05 03:13", output)
        self.assertIn("2026-09-18 11:56", output)
        self.assertIn("2027-02-24 15:58", output)

    def test_skill_uses_install_independent_paths(self):
        skill = (ROOT / "astrolab" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("${CLAUDE_SKILL_DIR}/scripts/astro_calc.py", skill)
        self.assertNotIn("python " + "scripts/astro_calc.py", skill)

    def test_cli_smoke_and_structured_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            chart = Path(directory) / "cli.chart.json"
            base = [sys.executable, str(SCRIPT)]
            commands = [
                base + ["--version"],
                base + ["natal", "--date", "1990-05-15", "--time", "14:30", "--tz-name", "Asia/Shanghai",
                        "--lat", "39.9", "--lon", "116.4", "--save", str(chart), "--json"],
                base + ["snapshot", "--natal", str(chart), "--date", "2026-07-14", "--time", "17:15", "--csv"],
                base + ["transits", "--natal", str(chart), "--start", "2026-01-01", "--end", "2026-12-31",
                        "--planets", "saturn,saturn", "--targets", "venus", "--aspects", "conjunction", "--quiet", "--json"],
                base + ["stations", "--start", "2026-01-01", "--end", "2026-12-31", "--tz", "8", "--json"],
                base + ["lunations", "--natal", str(chart), "--start", "2026-07-01", "--end", "2026-08-01", "--csv"],
                base + ["progressions", "--natal", str(chart), "--at", "2026-07-14", "--json"],
                base + ["ingresses", "--natal", str(chart), "--start", "2026-07-01", "--end", "2026-07-31",
                        "--bodies", "sun,saturn", "--kind", "both", "--json"],
                base + ["eclipses", "--natal", str(chart), "--start", "2026-01-01", "--end", "2026-12-31", "--json"],
                base + ["ephemeris", "status", "--destination", str(Path(directory) / "ephe"), "--json"],
            ]
            outputs = []
            for command in commands:
                result = subprocess.run(command, cwd=directory, text=True, encoding="utf-8",
                                        capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(result.stdout)
            self.assertEqual(outputs[0].strip(), "AstroLab 0.2.0")
            self.assertEqual(json.loads(outputs[1])["chart"]["schema_version"], 2)
            self.assertTrue(outputs[2].startswith("record_type,planet"))
            self.assertEqual(len(json.loads(outputs[3])["events"]), 2)
            self.assertIn("datetime,kind", outputs[5])
            self.assertEqual(len(json.loads(outputs[7])["events"]), 2)
            self.assertEqual(len(json.loads(outputs[8])["events"]), 4)
            self.assertFalse(json.loads(outputs[9])["complete"])

            broken = Path(directory) / "broken.json"
            broken.write_text('{"meta":{"tz":"bad"}}', encoding="utf-8")
            failure = subprocess.run(
                base + ["snapshot", "--natal", str(broken), "--date", "2026-07-14", "--time", "17:15"],
                cwd=directory, text=True, encoding="utf-8", capture_output=True, timeout=30,
            )
            self.assertNotEqual(failure.returncode, 0)
            self.assertIn("invalid natal chart", failure.stderr)
            self.assertNotIn("Traceback", failure.stderr)


if __name__ == "__main__":
    unittest.main()
