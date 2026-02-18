# Bot Queuing System

This document explains how the bot queuing system works.

## How It Works

The bot queuing system runs multiple bots in a continuous cycle. Here is the flow:

1. User selects which bots to run (by entering their numbers)
2. User provides login credentials (username and RSA passcode)
3. System creates a queue with the selected bots in the order specified
4. System runs each bot sequentially until it finishes
5. When a bot finishes, the system moves to the next bot in the queue
6. When all selected bots have run once, the system sleeps and then resets back to the first bot
7. The cycle repeats continuously

## Example

If you select bots 1, 4, and 2 in that order:

Cycle 1:
- Run Athena (bot 1) - checks for COVID-19 cases until none found, then sleeps and exits
- Run Strep (bot 4) - checks for Group A Strep cases until none found, then sleeps and exits
- Run Audrey (bot 2) - checks for Audrey cases until none found, then sleeps and exits
- All bots completed, reset to beginning

Cycle 2:
- Run Athena again
- Run Strep again
- Run Audrey again
- Reset to beginning again

This continues indefinitely until the program is manually stopped.

## The Queue Class

The BotQueue class manages the position in the queue:

- get_current_bot() - returns the bot at the current position
- get_next_bot() - moves to the next position and returns that bot
- reset_to_first() - moves back to the first position

When get_next_bot() reaches the end of the list, it wraps around to the first bot using modulo arithmetic.

## Bot Positions

Available bots and their selection numbers:

1. Athena - COVID-19 notification review
2. Audrey - General purpose bot
3. Anaplasma - Anaplasma case review
4. Strep - Group A Streptococcus case review
5. CovidEcr - COVID-19 ECR processing
6. HepBnotificationreview - Hepatitis B notification review
7. Gonorrhea - Gonorrhea case review
8. ILIOutbreak - Influenza-like illness outbreak review

## Changing Bot Order

To change the order that bots run, simply modify the bots dictionary in start_bots.py. For example:

Current:
  1: start_athena,
  2: start_audrey,
  4: start_strep,

To run strep immediately after athena instead of audrey:
  1: start_athena,
  2: start_strep,
  3: start_audrey,

Then select bots 1, 2, and 3 in order.

## What Happens When a Bot Finishes

When a bot finishes processing all available cases of its type:

1. It sends a manual review email notification
2. It calls NBS.Sleep() - this pauses for a configured duration
3. It breaks out of its processing loop and exits
4. The next bot in the queue automatically starts

## Continuous Cycling

After all selected bots have run once:

1. System prints "All bots completed. Resetting to first bot..."
2. Queue is reset to the first bot
3. All selected bots run again in the same order
4. This cycle repeats indefinitely

To stop the program, use Ctrl+C in the terminal.
