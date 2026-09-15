import esphome.codegen as cg
import esphome.config_validation as cv

# The screen's drawing code (display_ui.h) as a component rather than an
# `esphome: includes:` file. Includes resolve next to the top-level YAML,
# so a build that pulls the production YAML as a remote package (ESPHome
# Device Builder adoption) could not find the header; external components
# can come from a git ref instead. packages/ui-code-local.yaml and
# packages/ui-code-remote.yaml choose the source.

CODEOWNERS = []
DEPENDENCIES = ["display"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config):
    cg.add_global(cg.RawStatement('#include "esphome/components/dryer_ui/display_ui.h"'))
