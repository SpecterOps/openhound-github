from openhound.core.asset import EdgeDef

from openhound_github.kinds import edges as ek
from openhound_github.kinds import nodes as nk
from openhound_github.main import app
from openhound_github.models.enterprise_role_user import EnterpriseRoleUser


@app.asset(
    edges=[
        EdgeDef(
            start=nk.USER,
            end=nk.ENTERPRISE_ROLE,
            kind=ek.HAS_ROLE,
            description="Enterprise admin has owners role",
            traversable=True,
        ),
    ],
)
class EnterpriseAdmin(EnterpriseRoleUser):
    pass
