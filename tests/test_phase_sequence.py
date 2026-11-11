from traffic_model.domain import Controller, Phase
from traffic_model.phase_sequence import signal_runs


def controller():
    phases = (
        Phase("A", "C1", ("SG1", "SG2"), 20.0, 5.0),
        Phase("B", "C1", ("SG2", "SG3"), 25.0, 4.0),
        Phase("C", "C1", ("SG4",), 16.0, 10.0),
    )
    return Controller("C1", "I1", 80.0, 0.0, phases)


def test_overlap_is_one_continuous_run():
    runs = signal_runs(controller(), "SG2")
    assert len(runs) == 1
    assert runs[0].phase_ids == ("A", "B")
    assert runs[0].start_s == 0.0
    assert runs[0].end_s == 50.0
    assert runs[0].ending_intergreen_s == 4.0
