import { describeChange, describeDeviation, formatSigned, orderAngles, presentAction, presentAxis, presentDirection, presentLabel } from '@/src/presentation/format';

describe('presentation helpers', () => {
  test('maps backend enums to PT-BR without changing the source enum', () => {
    expect(presentDirection('DARKER')).toBe('MAIS ESCURA');
    expect(presentDirection('GREENER')).toBe('MAIS VERDE');
    expect(presentAction('MOVE_BLUER')).toBe('AZULAR');
    expect(presentAction('MIXED')).toBe('MISTO');
  });

  test('orders only the five required angles', () => {
    const values = [{ angle: 105 }, { angle: 25 }, { angle: 15 }, { angle: 75 }, { angle: 45 }];
    expect(orderAngles(values).map((item) => item.angle)).toEqual([15, 25, 45, 75, 105]);
  });

  test('formats delta signs only for presentation', () => {
    expect(formatSigned(0.12)).toBe('+0.120');
    expect(formatSigned(-2.668)).toBe('-2.668');
    expect(formatSigned(0)).toBe('0.000');
  });
});

describe('operator-facing names', () => {
  test('names each color axis by what it means', () => {
    expect(presentAxis('L')).toBe('Claro / escuro (L*)');
    expect(presentAxis('a')).toBe('Vermelho / verde (a*)');
  });

  test('describes differences to the target in words with PT-BR decimals', () => {
    expect(describeDeviation('L', -2)).toBe('2,00 mais escura que o alvo');
    expect(describeDeviation('A', 0.8)).toBe('0,80 mais vermelha que o alvo');
    expect(describeDeviation('B', -0.35)).toBe('0,35 mais azul que o alvo');
  });

  test('describes the change caused by an adjustment', () => {
    expect(describeChange('L', 0.5)).toBe('ficou 0,50 mais clara');
    expect(describeChange('B', 0.001)).toBe('não mudou');
  });

  test('translates enum names and keeps UNKNOWN contextual', () => {
    expect(presentLabel('POLYESTER_BASECOAT')).toBe('POLIÉSTER (BASE)');
    expect(presentLabel('WORSENED')).toBe('PIOROU');
    expect(presentLabel('UNKNOWN', 'NÃO SEI')).toBe('NÃO SEI');
  });
});
