import { formatSigned, orderAngles, presentAction, presentDirection } from '@/src/presentation/format';

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
