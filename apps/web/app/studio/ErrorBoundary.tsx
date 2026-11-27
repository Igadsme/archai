"use client"
import { Component, type ErrorInfo, type ReactNode } from "react"
import { Icon } from "./Icon"

type Props = { children: ReactNode; scope: string }
type State = { failed: boolean; detail: string }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false, detail: "" }

  static getDerivedStateFromError(error: Error): State {
    return { failed: true, detail: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[ArchAI:${this.props.scope}]`, error, info.componentStack)
  }

  componentDidUpdate(previous: Props) {
    if (previous.scope !== this.props.scope && this.state.failed) this.reset()
  }

  private reset = () => this.setState({ failed: false, detail: "" })

  render() {
    if (!this.state.failed) return this.props.children
    return <div className="boundary-state" role="alert">
      <span><Icon name="close" /></span>
      <div><small>WORKSPACE RECOVERY / {this.props.scope.toUpperCase()}</small><h2>This panel could not be rendered</h2><p>{this.state.detail || "An unexpected frontend error occurred."}</p></div>
      <button className="button" onClick={this.reset}>Retry panel</button>
    </div>
  }
}
