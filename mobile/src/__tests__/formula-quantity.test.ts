import {
  customQuantityMultiplier,
  customQuantityUnit,
  formulaQuantityOptions,
  scaleFormulaWeight,
} from '@/src/features/formulas/quantity';

describe('formula quantity standards', () => {
  test.each(['POLIESTER', 'LACA', 'ESMALTE_SINTETICO'] as const)(
    '%s uses quart standards',
    (system) => {
      expect(formulaQuantityOptions(system, 'DILUIDO').map((item) => item.label)).toEqual([
        '1 Quarto', '1/2 Quarto', '2 Quartos', '3 Quartos', '4 Quartos',
      ]);
    },
  );

  test('concentrated PU uses quart standards', () => {
    expect(formulaQuantityOptions('PU', 'CONCENTRADO').map((item) => item.label)).toEqual([
      '1 Quarto', '1/2 Quarto', '2 Quartos', '3 Quartos', '4 Quartos',
    ]);
  });

  test('diluted PU uses millilitre standards based on the 675 ml formula', () => {
    const options = formulaQuantityOptions('PU', 'DILUIDO');
    expect(options.map((item) => item.label)).toEqual([
      '675 ml', '337 ml', '1350 ml', '2025 ml', '2700 ml',
    ]);
    expect(options.map((item) => item.multiplier)).toEqual([1, 0.5, 2, 3, 4]);
  });

  test('scales and rounds component masses to four decimal places', () => {
    expect(scaleFormulaWeight('14', 0.5)).toBe('7');
    expect(scaleFormulaWeight('0.97', 0.5)).toBe('0.485');
    expect(scaleFormulaWeight('296.6', 4)).toBe('1186.4');
  });

  test('accepts any positive custom quantity using a comma or dot', () => {
    expect(customQuantityMultiplier('POLIESTER', 'DILUIDO', '1,5')).toBe(1.5);
    expect(customQuantityMultiplier('LACA', 'CONCENTRADO', '0.75')).toBe(0.75);
    expect(customQuantityMultiplier('PU', 'DILUIDO', '800')).toBeCloseTo(800 / 675);
    expect(customQuantityMultiplier('PU', 'DILUIDO', '0')).toBeNull();
    expect(customQuantityMultiplier('PU', 'DILUIDO', 'texto')).toBeNull();
  });

  test('selects the custom input unit from system and condition', () => {
    expect(customQuantityUnit('PU', 'DILUIDO')).toBe('ml');
    expect(customQuantityUnit('PU', 'CONCENTRADO')).toBe('Quartos');
    expect(customQuantityUnit('POLIESTER', 'DILUIDO')).toBe('Quartos');
  });
});
