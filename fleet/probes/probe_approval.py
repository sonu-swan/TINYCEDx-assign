import sys
sys.path.insert(0, ".")
from fleet.approval import ApprovalTrail

# Case 1: no approval at all -> must be refused
t1 = ApprovalTrail()
t1.start()
if t1.try_deliver():
    print("FAIL: delivered a record with no approval at all"); sys.exit(1)
print("OK: unapproved record refused delivery")

# Case 2: normal approval present, but high-value record missing the
# CASE_ID amendment's required second approver -> must still be refused
t2 = ApprovalTrail()
t2.start()
t2.approve("operator:reviewer")
if t2.try_deliver(role="compliance", threshold=10000, amount=50000):
    print("FAIL: delivered a high-value record without the amendment role's sign-off"); sys.exit(1)
print("OK: high-value record without amendment approval refused")

# Case 3: both approvals present -> delivery succeeds
t3 = ApprovalTrail()
t3.start()
t3.approve("operator:reviewer")
t3.amendment_approve("compliance", 10000, 50000, "operator")
if not t3.try_deliver(role="compliance", threshold=10000, amount=50000):
    print("FAIL: fully-approved record was refused"); sys.exit(1)
print("OK: fully-approved high-value record delivered")

print("PASS: probe-approval")
sys.exit(0)
