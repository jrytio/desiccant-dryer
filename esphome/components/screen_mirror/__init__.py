import esphome.codegen as cg
from esphome.components import web_server_base
from esphome.components.ili9xxx.display import ILI9XXXDisplay
from esphome.components.web_server_base import CONF_WEB_SERVER_BASE_ID
import esphome.config_validation as cv
from esphome.const import CONF_DISPLAY_ID, CONF_ID, CONF_PATH

# Serves an ili9xxx display's 8-bit frame buffer as a BMP on the web server.
# ESP32 only: the handler streams with esp_http_server directly so the
# 58 KB image never has to sit in RAM.

DEPENDENCIES = ["display"]
AUTO_LOAD = ["web_server_base"]

screen_mirror_ns = cg.esphome_ns.namespace("screen_mirror")
ScreenMirror = screen_mirror_ns.class_("ScreenMirror", cg.Component)


def _validate_path(value):
    value = cv.string_strict(value)
    if not value.startswith("/"):
        raise cv.Invalid("path must start with '/'")
    return value


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(ScreenMirror),
            cv.GenerateID(CONF_WEB_SERVER_BASE_ID): cv.use_id(
                web_server_base.WebServerBase
            ),
            cv.Required(CONF_DISPLAY_ID): cv.use_id(ILI9XXXDisplay),
            cv.Optional(CONF_PATH, default="/screen.bmp"): _validate_path,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    cv.only_on_esp32,
)


async def to_code(config):
    base = await cg.get_variable(config[CONF_WEB_SERVER_BASE_ID])
    var = cg.new_Pvariable(config[CONF_ID], base)
    await cg.register_component(var, config)
    disp = await cg.get_variable(config[CONF_DISPLAY_ID])
    cg.add(var.set_display(disp))
    cg.add(var.set_path(config[CONF_PATH]))
