import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type CurrencySwitcherProps = {
  value: string
  options: string[]
  onChange: (code: string) => void
}

export function CurrencySwitcher({ value, options, onChange }: CurrencySwitcherProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label="Валюта">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((code) => (
          <SelectItem key={code} value={code}>
            {code}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
