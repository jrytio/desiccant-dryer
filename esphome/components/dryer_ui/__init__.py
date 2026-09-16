import esphome.codegen as cg
import esphome.config_validation as cv

# The screen's drawing code (display_ui.h) as a component rather than an
# `esphome: includes:` file, so it can be shared via packages across the
# production, virtual, hw-test and host selectors. packages/ui-code-local.yaml
# chooses the source.

CODEOWNERS = []
DEPENDENCIES = ["display"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config):
    cg.add_global(cg.RawStatement('#include "esphome/components/dryer_ui/display_ui.h"'))
