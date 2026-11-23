import type { ComponentProps } from 'react'
import { Slot } from 'radix-ui'
import { cn } from 'cn'

type ButtonProps = ComponentProps<'button'> & {
  asChild?: boolean
  variant?: 'default' | 'outline' | 'secondary' | 'ghost' | 'destructive' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon' | 'icon-sm' | 'icon-xs' | 'xs'
}

export function Button({ asChild, variant = 'default', size = 'default', className, ...props }: ButtonProps) {
  const Component = asChild ? Slot.Root : 'button'
  return <Component data-slot="button" data-variant={variant} data-size={size} className={cn('sw-button', className)} {...props} />
}
