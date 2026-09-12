import { Link } from 'react-router-dom'

type LegalBackFrom = '/' | '/login' | '/register'

/** 登录 / 注册：同意《用户协议》与《隐私政策》 */
export default function AuthTermsAgree({
  checked,
  onCheckedChange,
  returnTo = '/login',
}: {
  checked: boolean
  onCheckedChange: (v: boolean) => void
  returnTo?: LegalBackFrom
}) {
  const linkState = { from: returnTo }

  return (
    <label className="flex items-start gap-2.5 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onCheckedChange(e.target.checked)}
        className="mt-0.5 size-4 shrink-0 rounded border-border accent-primary"
      />
      <span className="text-[12px] leading-relaxed text-muted-foreground">
        我已阅读并同意{' '}
        <Link
          to="/terms"
          state={linkState}
          className="text-primary font-medium hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          《用户服务协议》
        </Link>{' '}
        和{' '}
        <Link
          to="/privacy"
          state={linkState}
          className="text-primary font-medium hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          《隐私政策》
        </Link>
      </span>
    </label>
  )
}
