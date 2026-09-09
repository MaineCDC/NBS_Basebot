from tqdm import tqdm
import time
import traceback
from threading import Event
from custom_decorator import  error_handle
import os

def generator():
    while True:
        yield
is_in_production = os.getenv('ENVIRONMENT', 'production') != 'development'
@error_handle
def start_athena(username, password, login_complete: Event = None, is_logged_in=False):
    from .athena import Athena

    from bot_env import is_production, target_site_label
    print(f"[athena] target site: {target_site_label('athena')}")
    NBS = Athena(production=is_production('athena'))
    NBS.set_credentials(username, password)
    NBS.log_in(is_logged_in)
    if login_complete is not None:
        login_complete.set()
    NBS.GoToApprovalQueue()

    attempt_counter = 0
    # Names of COVID cases reviewed this pass that could NOT be actioned (e.g. the
    # case moved off the top before it could be rejected). Tracked so a stuck case
    # that keeps re-surfacing at the top isn't re-reviewed forever -- athena's loop
    # otherwise has NO iteration cap and would spin indefinitely on it.
    skipped_names = set()
    # Backstop so a stuck case can't loop forever (athena previously had no cap).
    limit = int(os.getenv("MAX_CASES_PER_PASS", "500000"))
    # Athena previously had NO exception handling around the loop body (the
    # try/except was commented out), so any per-case error ended the whole pass.
    # Count consecutive errors so a transient failure is retried but a persistently
    # broken/empty queue ends the pass cleanly.
    consecutive_errors = 0
    max_consecutive_errors = 5

    loop = tqdm(generator())
    for _ in loop:
        if loop.n >= limit:
            print("[athena] hit MAX_CASES_PER_PASS backstop; ending pass.")
            NBS.SendManualReviewEmail()
            return
        try:
            NBS.SortApprovalQueue()

            if NBS.queue_loaded:
                NBS.queue_loaded = None
                continue
            elif NBS.queue_loaded == False:
                # Queue failed to load. End this pass; the round-robin orchestrator
                # will re-run athena on the next cycle. (Previously this chained into
                # strep and Sleep()'d forever -- the shared-session loop runs strep as
                # its own entry, so athena just returns when it has no work.)
                NBS.queue_loaded = None
                NBS.SendManualReviewEmail()
                return
            NBS.CheckFirstCase()
            NBS.initial_name = NBS.patient_name
            if NBS.condition == '2019 Novel Coronavirus (2019-nCoV)':
                consecutive_errors = 0  # a real case was found and read
                # If the top case is one we already reviewed but could not action this
                # pass, no actionable COVID cases remain at the top -- end the pass so
                # the bot doesn't re-review the same stuck case forever.
                if NBS.initial_name and NBS.initial_name in skipped_names:
                    print(f"[athena] top case {NBS.initial_name!r} already reviewed/unactioned "
                          f"this pass; no actionable cases remain. Ending pass.")
                    NBS.SendManualReviewEmail()
                    return

                NBS.GoToFirstCaseInApprovalQueue()
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                NBS.StandardChecks()
                if not NBS.investigator:
                    NBS.TriageReview()
                elif NBS.investigator_name in NBS.outbreak_investigators:
                    NBS.OutbreakInvestigatorReview()
                else:
                    NBS.CaseInvestigatorReview()

                actioned = False
                if not NBS.issues:
                    NBS.ReturnApprovalQueue()
                    NBS.ApproveNotification()
                    actioned = True
                
                if NBS.queue_loaded:
                    NBS.queue_loaded = None
                    continue
                if len(NBS.issues) > 0:
                    NBS.SortApprovalQueue()
                    if NBS.queue_loaded:
                        NBS.queue_loaded = None
                        continue
                    NBS.CheckFirstCase()
                    NBS.final_name = NBS.patient_name
                    if NBS.final_name == NBS.initial_name:
                        NBS.RejectNotification()
                        actioned = True
                    elif NBS.final_name != NBS.initial_name:
                        print('Case at top of queue changed. No action was taken on the reviewed case.')
                        NBS.num_fail += 1

                if not actioned and NBS.initial_name:
                    # Couldn't action this case; remember it so it isn't re-reviewed
                    # indefinitely. It stays in the queue for a human to resolve.
                    skipped_names.add(NBS.initial_name)
            else:
                if attempt_counter < NBS.num_attempts:
                    attempt_counter += 1
                else:
                    # No COVID-19 cases left in the queue: this bot's pass is done.
                    # Return so the round-robin moves on to the next bot.
                    attempt_counter = 0
                    print("No COVID-19 cases in notification queue.")
                    NBS.SendManualReviewEmail()
                    return
        except Exception as e:
            # A case that raises MID-REVIEW is a "poison" case: record it (so the
            # skipped-names guard above ends the pass if it keeps surfacing) and
            # reset to a clean approval queue. Without this any per-case error
            # ended athena's whole pass.
            import traceback as _tb
            print(f"[athena] EXCEPTION on case: {e}")
            print(_tb.format_exc())
            consecutive_errors += 1
            if NBS.initial_name:
                skipped_names.add(NBS.initial_name)
            try:
                NBS.GoToApprovalQueue()
            except Exception as recover_err:
                print(f"[athena] queue recovery after exception failed: {recover_err}")
            if consecutive_errors >= max_consecutive_errors:
                print(f"[athena] {consecutive_errors} consecutive errors; queue appears "
                      f"empty/unstable. Ending pass.")
                NBS.SendManualReviewEmail()
                return
