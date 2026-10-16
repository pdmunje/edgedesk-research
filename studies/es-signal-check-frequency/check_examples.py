"""Small made-up cases checking timing, pauses and session-edge counting."""
import unittest
import pandas as pd
from reproduce import hold_to_quarter_hours, periods


class Examples(unittest.TestCase):
    def test_a_neutral_minute_splits_an_active_period(self):
        self.assertEqual(periods([1, 1, 0, 1, 1, -1, -1]), [2, 2, 2])

    def test_held_decision_ignores_intermediate_pause(self):
        times = pd.date_range('2026-01-05 10:00', periods=30, freq='min', tz='UTC')
        states = [1] * 30
        states[7] = 0
        held = hold_to_quarter_hours(states, times)
        self.assertEqual(periods(states), [7, 22])
        self.assertEqual(periods(held), [30])

    def test_neutral_at_check_time_is_held_for_fifteen_minutes(self):
        times = pd.date_range('2026-01-05 10:00', periods=45, freq='min', tz='UTC')
        states = [1] * 45
        states[15] = 0
        self.assertEqual(hold_to_quarter_hours(states, times).tolist(),
                         [1] * 15 + [0] * 15 + [1] * 15)

    def test_day_edges_are_counted_without_joining_days(self):
        self.assertEqual(periods([1] * 390), [390])
        self.assertEqual(periods([0] * 390), [])

    def test_direction_change_starts_another_period(self):
        self.assertEqual(periods([1] * 15 + [-1] * 15), [15, 15])


if __name__ == '__main__':
    unittest.main()
