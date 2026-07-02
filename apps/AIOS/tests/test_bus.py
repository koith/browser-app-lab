from aios.kernel.bus import Event, MessageBus


def test_exact_and_wildcard_subscription():
    bus = MessageBus()
    got = []
    bus.subscribe("task.created", lambda e: got.append(("exact", e.topic)))
    bus.subscribe("task.*", lambda e: got.append(("wild", e.topic)))
    bus.subscribe("*", lambda e: got.append(("all", e.topic)))
    bus.publish(Event("task.created", {}, correlation_id="t1"))
    bus.publish(Event("meeting.opened", {}, correlation_id="t1"))
    assert ("exact", "task.created") in got
    assert ("wild", "task.created") in got
    assert ("wild", "meeting.opened") not in got
    assert ("all", "meeting.opened") in got


def test_event_log_persisted(tmp_path):
    from aios.drivers.storage.json_store import JsonFileStorage
    s = JsonFileStorage(str(tmp_path))
    bus = MessageBus(storage=s)
    bus.publish(Event("task.created", {"x": 1}, correlation_id="t1"))
    assert len(s.query("events", topic="task.created")) == 1
