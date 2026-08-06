/**
 * Maps an ExpenseCategory's `icon` string (a lucide-react component name in kebab-case,
 * e.g. "shopping-cart") to the actual component, so both CategoryForm's icon picker and
 * anywhere a category badge is rendered (ExpenseCard, CategoryPicker) stay in sync off one
 * list instead of two copies drifting apart. Falls back to MoreHorizontal for any icon
 * name not in this curated set (e.g. a category created before this list grew, or data
 * that came from somewhere else) so a badge never renders with no icon at all.
 */
import {
  ShoppingCart,
  Utensils,
  Car,
  Film,
  ShoppingBag,
  Zap,
  HeartPulse,
  Plane,
  Repeat,
  Dumbbell,
  MoreHorizontal,
  Home,
  Briefcase,
  GraduationCap,
  PawPrint,
  Gift,
  Wrench,
  type LucideIcon,
} from 'lucide-react'

export const EXPENSE_CATEGORY_ICON_OPTIONS: { value: string; Icon: LucideIcon }[] = [
  { value: 'shopping-cart', Icon: ShoppingCart },
  { value: 'utensils', Icon: Utensils },
  { value: 'car', Icon: Car },
  { value: 'film', Icon: Film },
  { value: 'shopping-bag', Icon: ShoppingBag },
  { value: 'zap', Icon: Zap },
  { value: 'heart-pulse', Icon: HeartPulse },
  { value: 'plane', Icon: Plane },
  { value: 'repeat', Icon: Repeat },
  { value: 'dumbbell', Icon: Dumbbell },
  { value: 'home', Icon: Home },
  { value: 'briefcase', Icon: Briefcase },
  { value: 'graduation-cap', Icon: GraduationCap },
  { value: 'paw-print', Icon: PawPrint },
  { value: 'gift', Icon: Gift },
  { value: 'wrench', Icon: Wrench },
  { value: 'more-horizontal', Icon: MoreHorizontal },
]

const ICON_MAP: Record<string, LucideIcon> = Object.fromEntries(
  EXPENSE_CATEGORY_ICON_OPTIONS.map(({ value, Icon }) => [value, Icon])
)

export function getCategoryIcon(iconName: string | null | undefined): LucideIcon {
  return (iconName && ICON_MAP[iconName]) || MoreHorizontal
}
