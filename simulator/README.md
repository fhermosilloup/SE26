# Raspberry Pi simulador
En esta carpeta se encuentran las herramientas para realizar simulación de ```gpiozero``` con raspberry pi.
Para la simulación se cuenta con dos herramientas escenciales:
1. ```tkgpio designer```: Herramienta para diseñar el esquemático que se utilizará en la simulación.
2. ```tkgpio```: La herramienta que ejecuta el codigo de ```gpiozero``` e interactua con el esquemático.

## Instalación
1. Desde el entorno virtual de python, instalar la biblioteca tkgpio
```batch
pip install 'tkgpio[sound]'
```


## tkgpio designer
Para correr el designer
1. Descarga el archivo de python llamado ```tkgpio_designer.py```
2. Ejecutelo desde terminal (en cualquier sistema operativo) como:
```batch
python tkgpio_designer.py
```
3. Se abrira una ventana que contiene la interfaz donde podra elegir en la columna de la izquierda, los componentes que desea agregar a su simulación al dar clic en el mismo.
4. Esto agregara el elemento al espacio de trabajo (región cuadriculada)
5. Al agregar un componente, es posible darle clic para seleccionarlo, con esto, podra realizar varias acciones sobre el objeto
* Borrarlo: Dando clic al botón de ```Delete``` en su teclado.
* Copiar: Dando clic al botón de ```CTRL + C``` en su teclado.
* Mover: Dando clic a las flechas ```→ ↑ ↓ ←``` en su teclado. Tambien es posible moverlo si lo arrastra con el mouse.
* Deseleccionar: Dando clic al botón ```ESC``` en su teclado.
6. Cuando selecciona un componente en el espacio de trabajo, es posible editar algunas de sus propiedades, principalmente el pinout del elemento. Esto se realiza mediante las propiedades del componente que aparecen en la parte de la derecha de la ventana. Si las modifica, hay que dar clic al botón ```Aplicar``` para aplicar los cambios.
7. Una vez que ya creo y configuro su esquemático, podra realizar dos acciones principales:
  1. Exportar a .json, el cual contiene las conexiones y configuraciones de los pines de la raspberry pi. Importelo si quiere conservar el diagrama para posteriormente modificarlo en esta herramienta.
  2. Exportar a .py, el cual contiene el código básico para ejecutar la simulación desde python.
  
# tkgpio
Una vez creado el esquematico y exportado, por ejemplo a python, podra:
1. Modificar el código de python que se autogenero con el archivo exportado.
2. Correr la simulación desde terminal con el comando
```batch
python NOMBRE_DEL_ARCHIVO_DE_SIMULACIÓN.py
```
