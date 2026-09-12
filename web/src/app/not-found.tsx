import Link from "next/link"
import { Compass, FileQuestion } from "lucide-react"
import { SiteFooter } from "@/components/site/SiteFooter"
import { SiteHeader } from "@/components/site/SiteHeader"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function NotFound() {
  return <div className="flex min-h-screen flex-col"><SiteHeader /><main id="main-content" className="mx-auto flex w-full max-w-7xl flex-1 items-center px-4 py-12 sm:px-6 lg:px-8"><Card className="mx-auto w-full max-w-xl text-center"><CardHeader className="items-center"><FileQuestion className="size-10 text-muted-foreground" /><CardTitle className="text-4xl">Page not found</CardTitle><CardDescription>That context path does not exist. Start with the Studio, documentation, or the benchmark report.</CardDescription></CardHeader><CardContent className="flex justify-center gap-3"><Button render={<Link href="/" />}><Compass /> Return home</Button><Button variant="outline" render={<Link href="/docs" />}>Browse docs</Button></CardContent></Card></main><SiteFooter /></div>
}
