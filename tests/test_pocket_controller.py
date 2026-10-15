from sticky_intent.store import Store


def test_capture_is_independent_and_returns_to_icon(tmp_path):
    from sticky_intent.pocket import PocketController
    store = Store(tmp_path)
    original = store.add('Original')
    controller = PocketController(store)
    controller.select(original.id)
    controller.capture_draft = 'New\nexact draft'
    controller.capture_save()
    assert controller.mode == 'icon'
    assert controller.capture_draft == ''
    assert store.get(original.id).body == 'Original'
    assert store.list('all')[0].body == 'New\nexact draft'


def test_failed_capture_keeps_draft_and_surface(tmp_path):
    from sticky_intent.pocket import PocketController
    controller = PocketController(Store(tmp_path))
    controller.capture_draft = 'Keep me'
    controller.mode = 'capture'
    controller.store.add = lambda *a, **k: (_ for _ in ()).throw(OSError('Disk full'))
    assert not controller.capture_save()
    assert controller.capture_draft == 'Keep me'
    assert controller.mode == 'capture'
    assert 'Disk full' in controller.error


def test_conflict_retains_editor_and_blocks_minimise(tmp_path):
    from sticky_intent.pocket import PocketController
    store = Store(tmp_path)
    note = store.add('Original')
    controller = PocketController(store)
    controller.select(note.id)
    controller.body = 'Local edit'
    store.update(note.id, body='External edit')
    assert not controller.minimise()
    assert controller.body == 'Local edit'
    assert controller.mode == 'notes'
    assert store.get(note.id).body == 'External edit'


def test_interface_size_supports_25_to_200_and_legacy_collapse_opens_notes(tmp_path):
    import json
    from sticky_intent.pocket import PocketController
    store = Store(tmp_path)
    (store.home/'pocket-state.json').write_text(json.dumps({'mode':'collapsed','preferences':{'interface_size':25}}))
    controller = PocketController(store)
    assert controller.preferences['interface_size'] == 25
    assert controller.mode == 'notes'
    assert controller.transition('hud')
    assert controller.mode == 'hud'
    assert controller.transition('icon')
    assert controller.icon_restore == 'hud'
    for value in (25, 100, 200):
        assert controller.set_preference('interface_size', value)
    try:
        controller.set_preference('interface_size', 24)
    except ValueError:
        pass
    else:
        raise AssertionError('interface size below 25% must be rejected')
