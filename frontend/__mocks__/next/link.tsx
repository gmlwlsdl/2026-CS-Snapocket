import React from 'react'

interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  href: string
  children?: React.ReactNode
}

export default function Link({ href, children, ...rest }: LinkProps) {
  return React.createElement('a', { href, ...rest }, children)
}
