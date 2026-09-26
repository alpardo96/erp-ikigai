"""Pruebas de conversión de números a letras y generación de PDF."""
from decimal import Decimal
from django.test import TestCase
from core.utils.numeros_a_letras import numero_a_letras


class NumeroALetrasTests(TestCase):
    def test_cero(self):
        self.assertEqual(numero_a_letras(0), "CERO CON 00/100.-")
        self.assertEqual(numero_a_letras(Decimal('0.00')), "CERO CON 00/100.-")

    def test_unidades_y_decimales(self):
        self.assertEqual(numero_a_letras(1), "UN CON 00/100.-")
        self.assertEqual(numero_a_letras(15.50), "QUINCE CON 50/100.-")
        self.assertEqual(numero_a_letras("21.05"), "VEINTIUN CON 05/100.-")
        self.assertEqual(numero_a_letras(29.99), "VEINTINUEVE CON 99/100.-")

    def test_decenas_y_centenas(self):
        self.assertEqual(numero_a_letras(30), "TREINTA CON 00/100.-")
        self.assertEqual(numero_a_letras(35), "TREINTA Y CINCO CON 00/100.-")
        self.assertEqual(numero_a_letras(100), "CIEN CON 00/100.-")
        self.assertEqual(numero_a_letras(105), "CIENTO CINCO CON 00/100.-")
        self.assertEqual(numero_a_letras(520), "QUINIENTOS VEINTE CON 00/100.-")

    def test_miles_y_millones(self):
        self.assertEqual(numero_a_letras(1000), "UN MIL CON 00/100.-")
        self.assertEqual(numero_a_letras(1234.56), "UN MIL DOSCIENTOS TREINTA Y CUATRO CON 56/100.-")
        self.assertEqual(numero_a_letras(1000000), "UN MILLON CON 00/100.-")
        self.assertEqual(numero_a_letras(2500000), "DOS MILLONES QUINIENTOS MIL CON 00/100.-")
