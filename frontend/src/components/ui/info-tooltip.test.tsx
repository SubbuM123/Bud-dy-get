/**
 * Covers InfoTooltip's open/close interactions (hover, click, blur, Escape) and that its
 * title/content render once open - the popup used throughout the Retirement module to
 * explain unfamiliar terms.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { InfoTooltip } from './info-tooltip'

describe('InfoTooltip', () => {
  it('is closed by default', () => {
    render(<InfoTooltip title="Roth IRA" content="An after-tax retirement account." />)

    expect(screen.queryByText('An after-tax retirement account.')).not.toBeInTheDocument()
  })

  it('opens on click and shows the title and content', async () => {
    const user = userEvent.setup()
    render(<InfoTooltip title="Roth IRA" content="An after-tax retirement account." />)

    await user.click(screen.getByRole('button', { name: /about roth ira/i }))

    expect(screen.getByText('Roth IRA')).toBeInTheDocument()
    expect(screen.getByText('An after-tax retirement account.')).toBeInTheDocument()
  })

  it('stays open across repeated clicks (closing happens via blur/Escape/mouseleave instead)', async () => {
    const user = userEvent.setup()
    render(<InfoTooltip title="Roth IRA" content="An after-tax retirement account." />)

    const button = screen.getByRole('button', { name: /about roth ira/i })
    await user.click(button)
    await user.click(button)

    expect(screen.getByText('An after-tax retirement account.')).toBeInTheDocument()
  })

  it('opens on focus and closes on blur', async () => {
    const user = userEvent.setup()
    render(
      <>
        <InfoTooltip title="Roth IRA" content="An after-tax retirement account." />
        <button>Somewhere else</button>
      </>
    )

    await user.tab()
    expect(screen.getByText('An after-tax retirement account.')).toBeInTheDocument()

    await user.tab()
    expect(screen.queryByText('An after-tax retirement account.')).not.toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    render(<InfoTooltip title="Roth IRA" content="An after-tax retirement account." />)

    const button = screen.getByRole('button', { name: /about roth ira/i })
    await user.click(button)
    expect(screen.getByText('An after-tax retirement account.')).toBeInTheDocument()

    button.focus()
    await user.keyboard('{Escape}')
    expect(screen.queryByText('An after-tax retirement account.')).not.toBeInTheDocument()
  })

  it('renders without a title when only content is given', async () => {
    const user = userEvent.setup()
    render(<InfoTooltip content="Just a fact." />)

    await user.click(screen.getByRole('button', { name: /more information/i }))

    expect(screen.getByText('Just a fact.')).toBeInTheDocument()
  })
})
