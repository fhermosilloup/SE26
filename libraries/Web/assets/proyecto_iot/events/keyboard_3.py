# Controlador para el widget: keyboard_3


def on_key_pressed(context):
    widget_id = context.get('widget_id')
    value = context.get('value')
    ui = context.get('ui')
    # Ej Modify Properties: ui.set_property('label_0', 'label', 'Texto nuevo')
    # Ej Set Values: ui.set_value('led_0', True)
    texto=ui.get('textbox_2')
    if texto is not None:
    	ui.set_value('textbox_2', texto+str(value))
    else:
        ui.set_value('textbox_2', str(value))
    print('Evento on_key_pressed de ' + str(widget_id) + ' valor: ' + str(value))
