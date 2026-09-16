import esphome.codegen as cg
import esphome.config_validation as cv

# The screen's drawing code (display_ui.h) as a component rather than an
# `esphome: includes:` file: a component gets a real dependency on `display`
# and is compiled once per build with its include path set up, rather than
# relying on every selector spelling out the same include. It is wired in by
# packages/ui-code-local.yaml.

CODEOWNERS = []
DEPENDENCIES = ["display"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config):
    cg.add_global(cg.RawStatement('#include "esphome/components/dryer_ui/display_ui.h"'))
