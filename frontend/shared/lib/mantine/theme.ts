import { createTheme, type MantineColorsTuple, type CSSVariablesResolver } from '@mantine/core'

// Snapocket 시안 컬러 스케일 (#97C2EC 중심)
const snapCyan: MantineColorsTuple = [
  '#ebf4fb',
  '#d5e9f7',
  '#beddf4',
  '#a7d0ee',
  '#97c2ec', // shade 4 — 라이트 모드 primary
  '#7daed8',
  '#6399c3',
  '#4a85af',
  '#32709a',
  '#1b5c86',
]

export const theme = createTheme({
  primaryColor: 'snap',
  primaryShade: { light: 4, dark: 2 },

  colors: {
    snap: snapCyan,
  },

  fontFamily: 'var(--font-inter), Inter, sans-serif',
  fontFamilyMonospace: 'monospace',
  headings: {
    fontFamily: 'var(--font-manrope), Manrope, sans-serif',
  },

  defaultRadius: 'md',

  radius: {
    xs: '4px',
    sm: '8px',
    md: '10px',
    lg: '14px',
    xl: '20px',
  },

  components: {
    Input: {
      defaultProps: {
        variant: 'filled',
      },
    },
    TextInput: {
      defaultProps: {
        variant: 'filled',
      },
    },
    PasswordInput: {
      defaultProps: {
        variant: 'filled',
      },
    },
    Textarea: {
      defaultProps: {
        variant: 'filled',
      },
    },
    Select: {
      defaultProps: {
        variant: 'filled',
      },
    },
    Button: {
      defaultProps: {
        radius: 'xl',
      },
    },
    Modal: {
      defaultProps: {
        radius: 'lg',
        centered: true,
      },
    },
    Notification: {
      defaultProps: {
        radius: 'md',
      },
    },
  },
})

// Mantine 내장 CSS 변수를 our 테마 팔레트에 맞춤
export const cssVariablesResolver: CSSVariablesResolver = () => ({
  variables: {},
  light: {
    '--mantine-color-body': '#ffffff',
    '--mantine-color-text': '#1f1f1f',
    '--mantine-color-default': '#ede8df',
    '--mantine-color-default-hover': '#e4dfd5',
    '--mantine-color-default-border': 'rgba(162,155,144,0.3)',
    '--mantine-color-dimmed': '#4a4540',
    '--mantine-color-placeholder': 'rgba(74,69,64,0.45)',
    '--mantine-color-error': '#c62828',
  },
  dark: {
    '--mantine-color-body': '#0c0e11',
    '--mantine-color-text': '#f9f9fd',
    '--mantine-color-default': '#111417',
    '--mantine-color-default-hover': '#1a1d21',
    '--mantine-color-default-border': 'rgba(70,72,75,0.3)',
    '--mantine-color-dimmed': '#aaabaf',
    '--mantine-color-placeholder': 'rgba(170,171,175,0.35)',
    '--mantine-color-error': '#ef4444',
  },
})
