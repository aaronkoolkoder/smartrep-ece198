// Shared visual foundation for the Expo app (screens arrive in M5).
// System fonts preserve platform accessibility and do not need font downloads.
export const theme = {
  colors: {
    canvas: '#F7F8F2', surface: '#FFFFFF', ink: '#173C36',
    muted: '#526760', primary: '#24634F', onPrimary: '#FFFFFF',
    sage: '#E7F0E7', border: '#D5DFD7',
    success: '#24634F', successSurface: '#E7F0E7',
    warning: '#805100', warningSurface: '#FFF1CC',
    danger: '#A02E2E', dangerSurface: '#FCE8E6',
  },
  spacing: { xs: 8, sm: 16, md: 24, lg: 32, xl: 48 },
  radius: { control: 16, card: 24, pill: 999 },
  type: { body: 18, bodyLineHeight: 28, label: 18, heading: 32, headingLineHeight: 40, counter: 112 },
  control: { minHeight: 56, minWidth: 56 },
} as const;
