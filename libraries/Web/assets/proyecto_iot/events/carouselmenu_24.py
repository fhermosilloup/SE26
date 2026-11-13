# Controlador para el widget: carouselmenu_24


def on_item_click(context):
    widget_id = context.get('widget_id')
    value = context.get('value')
    ui = context.get('ui')
    # Ej Modify Properties: ui.set_property('label_0', 'label', 'Texto nuevo')
    # Ej Set Values: ui.set_value('led_0', True)
    print('Evento on_item_click de ' + str(widget_id) + ' valor: ' + str(value))
