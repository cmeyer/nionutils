import unittest

from nion.utils import Color


class TestColorClass(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_hex_color_from_named_color(self) -> None:
        self.assertEqual("#d8bfd8", Color.Color("thistle").hex_color_str)
        self.assertEqual("#123456", Color.Color("#123456").hex_color_str)
        self.assertEqual("#80123456", Color.Color("#80123456").hex_color_str)
        self.assertEqual("#123", Color.Color("#123").hex_color_str)
        self.assertEqual("#8123", Color.Color("#8123").hex_color_str)
        self.assertEqual("#ff000080", Color.Color("rgba(255, 0, 0, 0.5)").hex_color_str)
        self.assertEqual("#d8bfd8", Color.Color("rgb(216, 191, 216)").to_color_without_alpha().color_str)
        self.assertEqual("#d8bfd8", Color.Color("rgba(216, 191, 216, 0.5)").to_color_without_alpha().color_str)
        self.assertEqual(None, Color.Color(None).hex_color_str)

    def test_color_to_named_color(self) -> None:
        self.assertEqual("thistle", Color.Color("thistle").to_named_color_without_alpha().color_str)
        self.assertEqual("thistle", Color.Color("#d8bfd8").to_named_color_without_alpha().color_str)
        self.assertEqual("thistle", Color.Color("#d8bfd880").to_named_color_without_alpha().color_str)
        self.assertEqual("thistle", Color.Color("#d8bfd8").to_named_color_without_alpha().color_str)
        self.assertEqual("thistle", Color.Color("rgb(216, 191, 216)").to_named_color_without_alpha().color_str)
        self.assertEqual("thistle", Color.Color("rgba(216, 191, 216, 0.5)").to_named_color_without_alpha().color_str)
        self.assertEqual(None, Color.Color().to_named_color_without_alpha().color_str)

    def test_color_without_alpha(self) -> None:
        self.assertEqual("thistle", Color.Color("thistle").to_color_without_alpha().color_str)
        self.assertEqual("#123456", Color.Color("#123456").to_color_without_alpha().color_str)
        self.assertEqual("#123456", Color.Color("#12345680").to_color_without_alpha().color_str)
        self.assertEqual("#123", Color.Color("#123").to_color_without_alpha().color_str)
        self.assertEqual("#123", Color.Color("#1238").to_color_without_alpha().color_str)
        self.assertEqual("#d8bfd8", Color.Color("rgb(216, 191, 216)").to_color_without_alpha().color_str)
        self.assertEqual("#d8bfd8", Color.Color("rgba(216, 191, 216, 0.5)").to_color_without_alpha().color_str)
        self.assertEqual(None, Color.Color(None).to_color_without_alpha().color_str)

    def test_color_with_alpha(self) -> None:
        self.assertEqual("rgba(216,191,216,0.25)", Color.Color("thistle").to_color_with_alpha(0.25).color_str)
        self.assertEqual("rgba(216,191,216,1.0)", Color.Color("thistle").to_color_with_alpha(1.00).color_str)
        self.assertEqual("rgba(216,191,216,0.0)", Color.Color("thistle").to_color_with_alpha(0.00).color_str)
        self.assertEqual("rgba(216,191,216,0.75)", Color.Color("#d8bfd8").to_color_with_alpha(0.75).color_str)
        self.assertEqual("rgba(34,68,102,0.5)", Color.Color("#246").to_color_with_alpha(0.50).color_str)
        self.assertEqual("rgba(34,68,102,1.0)", Color.Color("#246").to_color_with_alpha(1.50).color_str)
        self.assertEqual("rgba(34,68,102,0.0)", Color.Color("#246").to_color_with_alpha(-1.50).color_str)

    def test_rgba_gives_alpha_from_0_to_1_last_as_in_css(self) -> None:
        self.assertEqual((255, 0, 0, 0.5), Color.Color("rgba(255, 0, 0, 0.5)").to_rgba())
        self.assertEqual((255, 0, 0, 128 / 255), Color.Color("#ff000080").to_rgba())
        self.assertEqual((255, 0, 0, 136 / 255), Color.Color("#f008").to_rgba())
        self.assertEqual((255, 0, 0, 1.0), Color.Color("red").to_rgba())
        self.assertEqual((255, 0, 0), Color.Color("#ff000080").to_rgb_255())
        self.assertEqual((255, 0, 0, 1.0), Color.Color("rgba(255, 0, 0, 2)").to_rgba())

    def test_transparent_is_transparent_black(self) -> None:
        self.assertEqual((0, 0, 0, 0.0), Color.Color("transparent").to_rgba())
        self.assertEqual("#000000", Color.Color("transparent").to_color_without_alpha().color_str)
        self.assertEqual(Color.Color("#00000000"), Color.Color("transparent"))

    def test_matches_without_alpha(self) -> None:
        self.assertTrue(Color.Color("thistle").matches_without_alpha(Color.Color("#d8bfd8")))
        self.assertTrue(Color.Color("thistle").matches_without_alpha(Color.Color("rgb(216, 191, 216)")))
        self.assertTrue(Color.Color("thistle").matches_without_alpha(Color.Color("rgba(216, 191, 216, 0.5)")))
        self.assertTrue(Color.Color("rgb(216, 191, 216)").matches_without_alpha(Color.Color("rgba(216, 191, 216, 0.5)")))
        self.assertTrue(Color.Color("#123").matches_without_alpha(Color.Color("#112233")))
        self.assertTrue(Color.Color("#123").matches_without_alpha(Color.Color("#11223380")))
        self.assertTrue(Color.Color("#1238").matches_without_alpha(Color.Color("#11223380")))
        self.assertTrue(Color.Color("#1238").matches_without_alpha(Color.Color("#112233")))

    def test_color_equals(self) -> None:
        self.assertEqual(Color.Color("thistle"), Color.Color("#d8bfd8"))
        self.assertEqual(Color.Color("rgba(255, 0, 0, 0.5)"), Color.Color("#ff000080"))
        self.assertNotEqual(Color.Color("rgb(216, 191, 216)"), Color.Color("rgba(216, 191, 216, 0.5)"))

    def test_color_hash(self) -> None:
        d = {Color.Color("thistle"): Color.Color("#d8bfd8")}
        self.assertEqual(d[Color.Color("thistle")], Color.Color("#d8bfd8"))
