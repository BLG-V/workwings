import { Link, useLocation } from 'react-router-dom'
import { LogIn, UserPlus } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

/** 未登录发消息时的引导弹窗 */
export default function LoginGateDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const location = useLocation()
  const from = location.pathname || '/chat'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle>登录后继续对话</DialogTitle>
          <DialogDescription className="text-[13px] leading-relaxed pt-1">
            你已进入智流主对话。发送消息、调用模型与联网能力需要先登录账号；注册需完成邮箱验证。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-col gap-2 sm:flex-col sm:space-x-0">
          <Button asChild className="w-full h-10 rounded-xl pressable">
            <Link to="/login" state={{ from }} onClick={() => onOpenChange(false)}>
              <LogIn className="size-4 mr-2" />
              去登录
            </Link>
          </Button>
          <Button
            asChild
            variant="secondary"
            className="w-full h-10 rounded-xl pressable"
          >
            <Link
              to="/register"
              state={{ from }}
              onClick={() => onOpenChange(false)}
            >
              <UserPlus className="size-4 mr-2" />
              注册账号
            </Link>
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="w-full h-9 rounded-xl text-muted-foreground"
            onClick={() => onOpenChange(false)}
          >
            先逛逛
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
