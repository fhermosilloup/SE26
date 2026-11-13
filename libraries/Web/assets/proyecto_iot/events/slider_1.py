# Controlador para el widget: slider_1


def on_value_change(context):
    widget_id = context.get('widget_id')
    value = context.get('value')
    ui = context.get('ui')
    # Ej: ui.set_property('label_0', 'label', 'Texto nuevo')
    print('Evento on_value_change de ' + str(widget_id) + ' valor: ' + str(value))
