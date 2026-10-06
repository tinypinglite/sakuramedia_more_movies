import json
from pathlib import Path

from sakuramedia_more_movies import plugin
from sakuramedia_more_movies.plugin import PLUGIN_ID, register

from src.plugins import PluginContext
from src.plugins.loader import load_plugin_settings_model


def test_settings_model_resolves_from_package_root():
    model = load_plugin_settings_model(Path(__file__).parents[1])
    assert model is not None
    assert "min_heat" in model.model_fields


def test_manifest_matches_plugin_module():
    manifest = json.loads(
        (Path(plugin.__file__).parent / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["plugin_id"] == PLUGIN_ID
    assert manifest["version"] == plugin.__version__
    assert manifest["settings_model"] == "MoreMoviesSettings"


def test_register_declares_sync_job():
    context = PluginContext(
        plugin_id=PLUGIN_ID,
        settings={},
        data_dir=Path("/tmp/more-movies-test"),
    )
    registration = register(context)
    assert registration.plugin_id == "sakuramedia_more_movies"
    assert registration.display_name == "SakuraMedia 更多影片"
    assert [job.task_key for job in registration.jobs] == [
        "sakuramedia_more_movies_sync"
    ]
    job = registration.jobs[0]
    assert job.default_cron == "0 6 * * *"
    assert callable(job.handler)
