import esphome.codegen as cg
from esphome.components import web_server_base
from esphome.components.display import Display
from esphome.components.web_server_base import CONF_WEB_SERVER_BASE_ID
import esphome.config_validation as cv
from esphome.const import CONF_DISPLAY_ID, CONF_ID, CONF_PATH

# Serves the current screen as an 8-bit indexed PNG on the web server. The
# frame is re-rendered on demand from dryer_ui::last_state() rather than read
# out of a display driver, so this works with any driver and with a partial
# driver frame buffer. ESP32 only: the handler streams with esp_http_server
# directly so the 58 KB image never has to sit in RAM.

DEPENDENCIES = ["display", "dryer_ui"]
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
            cv.Required(CONF_DISPLAY_ID): cv.use_id(Display),
            cv.Optional(CONF_PATH, default="/screen.png"): _validate_path,
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
