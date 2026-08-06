from app.application.interfaces.authorization_checker import AuthorizationChecker, AuthorizationContext


class RBACAuthorizationChecker(AuthorizationChecker):
    async def has_role(self, ctx: AuthorizationContext, role_name: str) -> bool:
        return ctx.role_name == role_name

    async def has_permission(self, ctx: AuthorizationContext, permission_name: str) -> bool:
        return permission_name in ctx.permissions
