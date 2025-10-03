/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Dashboard Component for Sucursales y Cajas
 * Compatible with Odoo 17 CE
 */
class SucursalesCajasDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        
        this.state = useState({
            loading: true,
            stats: {
                totalOperations: 0,
                deposits: 0,
                withdrawals: 0,
                pending: 0,
                activeSessions: 0,
                totalCashboxes: 0
            },
            activeCashboxes: [],
            pendingOperations: [],
            recentOperations: [],
            branches: [],
            lastUpdate: new Date()
        });

        // Auto-refresh interval (30 seconds)
        this.refreshInterval = null;
        
        onMounted(() => {
            this.loadDashboardData();
            this.startAutoRefresh();
        });
        
        onWillUnmount(() => {
            this.stopAutoRefresh();
        });
    }

    /**
     * Load all dashboard data
     */
    async loadDashboardData() {
        this.state.loading = true;
        try {
            await Promise.all([
                this.loadStatistics(),
                this.loadActiveCashboxes(),
                this.loadPendingOperations(),
                this.loadRecentOperations(),
                this.loadBranches()
            ]);
            this.state.lastUpdate = new Date();
        } catch (error) {
            this.notification.add("Error al cargar el dashboard", {
                type: "danger",
                sticky: false
            });
            console.error("Dashboard loading error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Load dashboard statistics
     */
    async loadStatistics() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const todayStr = today.toISOString().split('T')[0];
        
        // Get operations count for today
        const operations = await this.orm.searchRead(
            "sucursales_cajas.operation",
            [["create_date", ">=", todayStr + " 00:00:00"]],
            ["operation_type", "state"]
        );
        
        this.state.stats.totalOperations = operations.length;
        this.state.stats.deposits = operations.filter(op => op.operation_type === "deposit").length;
        this.state.stats.withdrawals = operations.filter(op => op.operation_type === "withdrawal").length;
        this.state.stats.pending = operations.filter(op => op.state === "pending").length;
        
        // Get active sessions
        const sessions = await this.orm.searchCount(
            "sucursales_cajas.session",
            [["state", "in", ["open", "closing"]]]
        );
        this.state.stats.activeSessions = sessions;
        
        // Get total cashboxes
        const cashboxes = await this.orm.searchCount(
            "sucursales_cajas.cashbox",
            [["active", "=", true]]
        );
        this.state.stats.totalCashboxes = cashboxes;
    }

    /**
     * Load active cashboxes with sessions
     */
    async loadActiveCashboxes() {
        const cashboxes = await this.orm.searchRead(
            "sucursales_cajas.cashbox",
            [["state", "=", "in_session"]],
            ["display_name", "session_user_id", "pending_operations_count", "active_session_id"],
            { limit: 10 }
        );
        
        this.state.activeCashboxes = cashboxes;
    }

    /**
     * Load pending operations
     */
    async loadPendingOperations() {
        const operations = await this.orm.searchRead(
            "sucursales_cajas.operation",
            [["state", "=", "pending"]],
            ["name", "partner_id", "operation_type", "currency_type", "amount", "cashbox_id", "request_date"],
            { order: "request_date asc", limit: 10 }
        );
        
        this.state.pendingOperations = operations;
    }

    /**
     * Load recent operations
     */
    async loadRecentOperations() {
        const operations = await this.orm.searchRead(
            "sucursales_cajas.operation",
            [],
            ["name", "partner_id", "operation_type", "currency_type", "amount", "state", "completion_date"],
            { order: "create_date desc", limit: 10 }
        );
        
        this.state.recentOperations = operations;
    }

    /**
     * Load branches summary
     */
    async loadBranches() {
        const branches = await this.orm.searchRead(
            "sucursales_cajas.branch",
            [["active", "=", true]],
            ["name", "cashbox_count"],
            { order: "name" }
        );
        
        this.state.branches = branches;
    }

    /**
     * Start auto-refresh timer
     */
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            this.loadDashboardData();
        }, 30000); // 30 seconds
    }

    /**
     * Stop auto-refresh timer
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * Manual refresh
     */
    async onRefresh() {
        await this.loadDashboardData();
        this.notification.add("Dashboard actualizado", {
            type: "success",
            sticky: false
        });
    }

    /**
     * Open new operation wizard
     */
    async onNewOperation() {
        const action = {
            type: "ir.actions.act_window",
            name: "Nueva Operación",
            res_model: "sucursales_cajas.send_to_cashbox_wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {}
        };
        this.action.doAction(action);
    }

    /**
     * View active cashboxes
     */
    onViewActiveCashboxes() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Cajas Activas",
            res_model: "sucursales_cajas.cashbox",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "=", "in_session"]],
            target: "current"
        });
    }

    /**
     * View pending operations
     */
    onViewPendingOperations() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Operaciones Pendientes",
            res_model: "sucursales_cajas.operation",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "=", "pending"]],
            target: "current"
        });
    }

    /**
     * Format currency amount
     */
    formatAmount(amount, currency) {
        const formatter = new Intl.NumberFormat('es-AR', {
            style: 'currency',
            currency: currency === 'USD' ? 'USD' : 'ARS',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        
        if (currency === 'USDT') {
            return `USDT ${amount.toFixed(2)}`;
        }
        
        return formatter.format(amount);
    }

    /**
     * Format datetime
     */
    formatDateTime(datetime) {
        if (!datetime) return '';
        
        const date = new Date(datetime);
        const now = new Date();
        const diff = now - date;
        
        // Less than 1 hour ago
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `hace ${minutes} minuto${minutes !== 1 ? 's' : ''}`;
        }
        
        // Less than 24 hours ago
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `hace ${hours} hora${hours !== 1 ? 's' : ''}`;
        }
        
        // Format as date
        return date.toLocaleDateString('es-AR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * Get operation type icon
     */
    getOperationIcon(type) {
        const icons = {
            deposit: 'fa-arrow-down text-success',
            withdrawal: 'fa-arrow-up text-danger',
            transfer_in: 'fa-arrow-right text-info',
            transfer_out: 'fa-arrow-left text-warning'
        };
        return icons[type] || 'fa-exchange';
    }

    /**
     * Get state badge class
     */
    getStateBadgeClass(state) {
        const classes = {
            draft: 'badge-secondary',
            pending: 'badge-warning',
            processing: 'badge-info',
            done: 'badge-success',
            cancelled: 'badge-danger'
        };
        return `badge ${classes[state] || 'badge-secondary'}`;
    }
}

SucursalesCajasDashboard.template = "sucursales_cajas.Dashboard";

// Register as action
registry.category("actions").add("sucursales_cajas_dashboard", SucursalesCajasDashboard);