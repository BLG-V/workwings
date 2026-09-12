import { Link } from 'react-router-dom'
import { Home, AlertTriangle, LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { isAuthenticated } from '@/lib/auth'

export default function NotFoundPage() {
  const loggedIn = isAuthenticated()

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="text-center">
        <div className="size-20 mx-auto rounded-full bg-accent flex items-center justify-center mb-6">
          <AlertTriangle className="size-10 text-muted-foreground" />
        </div>
        <h1 className="text-6xl font-bold mb-4">404</h1>
        <p className="text-lg text-muted-foreground mb-8">
          抱歉，你访问的页面不存在
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button asChild>
            <Link to={loggedIn ? '/chat' : '/login'}>
              {loggedIn ? (
                <>
                  <Home className="size-4 mr-2" />
                  返回首页
                </>
              ) : (
                <>
                  <LogIn className="size-4 mr-2" />
                  去登录
                </>
              )}
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
