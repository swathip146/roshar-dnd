"""
Debug Support Module
Provides comprehensive debugging and monitoring capabilities for the D&D Assistant system
"""
import logging
import time
import json
import traceback
from typing import Dict, List, Any, Optional
from functools import wraps
from datetime import datetime
import os


class DnDAssistantLogger:
    """Enhanced logging system for D&D Assistant"""
    
    def __init__(self, log_level: str = "INFO", log_file: str = "dnd_assistant.log"):
        self.log_file = log_file
        self.setup_logging(log_level)
        self.performance_logs = []
        self.error_logs = []
        self.agent_activity = {}
    
    def setup_logging(self, log_level: str):
        """Setup comprehensive logging configuration"""
        # Create logs directory if it doesn't exist
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, self.log_file)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )
        
        # Create specialized loggers
        self.system_logger = logging.getLogger("DnD.System")
        self.agent_logger = logging.getLogger("DnD.Agents")
        self.performance_logger = logging.getLogger("DnD.Performance")
        self.user_action_logger = logging.getLogger("DnD.UserActions")
        self.error_logger = logging.getLogger("DnD.Errors")
    
    def log_user_action(self, action: str, params: Dict[str, Any], result: str, duration: float):
        """Log user actions with results"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "parameters": params,
            "result_preview": result[:200] + "..." if len(result) > 200 else result,
            "duration_ms": round(duration * 1000, 2),
            "success": "❌" not in result and "Failed" not in result
        }
        
        self.user_action_logger.info(f"USER_ACTION: {json.dumps(log_entry, indent=2)}")
    
    def log_agent_activity(self, agent_id: str, action: str, data: Dict[str, Any], success: bool, duration: float):
        """Log agent activity and performance"""
        if agent_id not in self.agent_activity:
            self.agent_activity[agent_id] = {
                "total_actions": 0,
                "successful_actions": 0,
                "total_duration": 0,
                "average_duration": 0,
                "last_activity": None
            }
        
        # Update activity stats
        stats = self.agent_activity[agent_id]
        stats["total_actions"] += 1
        if success:
            stats["successful_actions"] += 1
        stats["total_duration"] += duration
        stats["average_duration"] = stats["total_duration"] / stats["total_actions"]
        stats["last_activity"] = datetime.now().isoformat()
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "action": action,
            "data_keys": list(data.keys()) if data else [],
            "success": success,
            "duration_ms": round(duration * 1000, 2)
        }
        
        self.agent_logger.info(f"AGENT_ACTION: {json.dumps(log_entry)}")
    
    def log_performance_metric(self, metric_name: str, value: float, context: Dict[str, Any] = None):
        """Log performance metrics"""
        metric_entry = {
            "timestamp": datetime.now().isoformat(),
            "metric": metric_name,
            "value": value,
            "context": context or {}
        }
        
        self.performance_logs.append(metric_entry)
        self.performance_logger.info(f"PERFORMANCE: {json.dumps(metric_entry)}")
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None, agent_id: str = None):
        """Log errors with full context"""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "agent_id": agent_id,
            "context": context or {}
        }
        
        self.error_logs.append(error_entry)
        self.error_logger.error(f"ERROR: {json.dumps(error_entry, indent=2)}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics"""
        if not self.performance_logs:
            return {"message": "No performance data available"}
        
        recent_logs = self.performance_logs[-100:]  # Last 100 entries
        
        summary = {
            "total_metrics": len(self.performance_logs),
            "recent_metrics": len(recent_logs),
            "agent_activity": self.agent_activity,
            "error_count": len(self.error_logs),
            "average_response_times": {}
        }
        
        # Calculate average response times by metric type
        response_times = {}
        for log in recent_logs:
            metric = log["metric"]
            if metric not in response_times:
                response_times[metric] = []
            response_times[metric].append(log["value"])
        
        for metric, times in response_times.items():
            summary["average_response_times"][metric] = sum(times) / len(times)
        
        return summary
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics"""
        if not self.error_logs:
            return {"message": "No errors logged"}
        
        error_types = {}
        agent_errors = {}
        recent_errors = self.error_logs[-20:]  # Last 20 errors
        
        for error in self.error_logs:
            error_type = error["error_type"]
            agent_id = error.get("agent_id", "unknown")
            
            error_types[error_type] = error_types.get(error_type, 0) + 1
            agent_errors[agent_id] = agent_errors.get(agent_id, 0) + 1
        
        return {
            "total_errors": len(self.error_logs),
            "error_types": error_types,
            "errors_by_agent": agent_errors,
            "recent_errors": [
                {
                    "timestamp": err["timestamp"],
                    "type": err["error_type"],
                    "message": err["error_message"],
                    "agent": err.get("agent_id", "unknown")
                }
                for err in recent_errors
            ]
        }


def debug_monitor(logger: DnDAssistantLogger):
    """Decorator for monitoring function performance and errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = func.__name__
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log successful execution
                logger.log_performance_metric(
                    f"function_{function_name}",
                    duration,
                    {"args_count": len(args), "kwargs_count": len(kwargs)}
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Log error with context
                context = {
                    "function": function_name,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                    "duration": duration
                }
                
                logger.log_error(e, context)
                raise
        
        return wrapper
    return decorator


class SystemHealthMonitor:
    """Monitor system health and performance"""
    
    def __init__(self, logger: DnDAssistantLogger):
        self.logger = logger
        self.health_checks = {}
        self.system_metrics = {
            "uptime": time.time(),
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0
        }
    
    def add_health_check(self, name: str, check_function: callable):
        """Add a health check function"""
        self.health_checks[name] = check_function
    
    def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = {}
        overall_health = True
        
        for name, check_func in self.health_checks.items():
            try:
                start_time = time.time()
                result = check_func()
                duration = time.time() - start_time
                
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "result": result,
                    "duration_ms": round(duration * 1000, 2)
                }
                
                if not result:
                    overall_health = False
                    
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "duration_ms": 0
                }
                overall_health = False
                
                self.logger.log_error(e, {"health_check": name})
        
        results["overall_health"] = "healthy" if overall_health else "unhealthy"
        results["timestamp"] = datetime.now().isoformat()
        
        return results
    
    def update_request_metrics(self, success: bool):
        """Update request metrics"""
        self.system_metrics["total_requests"] += 1
        if success:
            self.system_metrics["successful_requests"] += 1
        else:
            self.system_metrics["failed_requests"] += 1
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        current_time = time.time()
        uptime_seconds = current_time - self.system_metrics["uptime"]
        
        metrics = self.system_metrics.copy()
        metrics.update({
            "uptime_seconds": uptime_seconds,
            "uptime_hours": uptime_seconds / 3600,
            "success_rate": (
                self.system_metrics["successful_requests"] / 
                max(self.system_metrics["total_requests"], 1)
            ) * 100,
            "current_timestamp": datetime.now().isoformat()
        })
        
        return metrics


class DebugCommands:
    """Debug commands for the D&D Assistant"""
    
    def __init__(self, logger: DnDAssistantLogger, health_monitor: SystemHealthMonitor):
        self.logger = logger
        self.health_monitor = health_monitor
    
    def get_debug_status(self) -> str:
        """Get comprehensive debug status"""
        health_results = self.health_monitor.run_health_checks()
        performance_summary = self.logger.get_performance_summary()
        error_summary = self.logger.get_error_summary()
        system_metrics = self.health_monitor.get_system_metrics()
        
        status = "🔧 **SYSTEM DEBUG STATUS**\n\n"
        
        # System Health
        health_emoji = "🟢" if health_results["overall_health"] == "healthy" else "🔴"
        status += f"**Overall Health:** {health_emoji} {health_results['overall_health'].title()}\n\n"
        
        # Health Checks
        if len(health_results) > 2:  # More than just overall_health and timestamp
            status += "**Health Checks:**\n"
            for name, result in health_results.items():
                if name not in ["overall_health", "timestamp"]:
                    emoji = "✅" if result["status"] == "healthy" else "❌"
                    status += f"  {emoji} {name}: {result['status']} ({result.get('duration_ms', 0)}ms)\n"
            status += "\n"
        
        # System Metrics
        status += "**System Metrics:**\n"
        status += f"  • Uptime: {system_metrics['uptime_hours']:.1f} hours\n"
        status += f"  • Total Requests: {system_metrics['total_requests']}\n"
        status += f"  • Success Rate: {system_metrics['success_rate']:.1f}%\n\n"
        
        # Agent Activity
        if performance_summary.get("agent_activity"):
            status += "**Agent Activity:**\n"
            for agent_id, stats in performance_summary["agent_activity"].items():
                success_rate = (stats["successful_actions"] / max(stats["total_actions"], 1)) * 100
                status += f"  • {agent_id}: {stats['total_actions']} actions ({success_rate:.1f}% success)\n"
            status += "\n"
        
        # Performance Summary
        if performance_summary.get("average_response_times"):
            status += "**Average Response Times:**\n"
            for metric, avg_time in performance_summary["average_response_times"].items():
                status += f"  • {metric}: {avg_time:.3f}s\n"
            status += "\n"
        
        # Recent Errors
        if error_summary.get("recent_errors"):
            status += f"**Recent Errors ({error_summary['total_errors']} total):**\n"
            for error in error_summary["recent_errors"][-5:]:  # Last 5 errors
                status += f"  • {error['timestamp'][:19]}: {error['type']} in {error['agent']}\n"
            status += "\n"
        
        status += f"*Debug report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        
        return status
    
    def get_agent_debug_info(self, agent_id: str) -> str:
        """Get debug information for a specific agent"""
        agent_stats = self.logger.agent_activity.get(agent_id, {})
        
        if not agent_stats:
            return f"❌ No debug information available for agent: {agent_id}"
        
        info = f"🎭 **DEBUG INFO: {agent_id.upper()}**\n\n"
        info += f"**Activity Statistics:**\n"
        info += f"  • Total Actions: {agent_stats['total_actions']}\n"
        info += f"  • Successful Actions: {agent_stats['successful_actions']}\n"
        info += f"  • Success Rate: {(agent_stats['successful_actions'] / max(agent_stats['total_actions'], 1)) * 100:.1f}%\n"
        info += f"  • Average Duration: {agent_stats['average_duration']:.3f}s\n"
        info += f"  • Last Activity: {agent_stats['last_activity']}\n\n"
        
        # Recent errors for this agent
        agent_errors = [err for err in self.logger.error_logs if err.get("agent_id") == agent_id]
        if agent_errors:
            info += f"**Recent Errors ({len(agent_errors)} total):**\n"
            for error in agent_errors[-3:]:  # Last 3 errors
                info += f"  • {error['timestamp'][:19]}: {error['error_type']}\n"
                info += f"    Message: {error['error_message'][:100]}...\n"
        else:
            info += "**No errors recorded for this agent** ✅\n"
        
        return info
    
    def clear_debug_logs(self) -> str:
        """Clear debug logs"""
        self.logger.performance_logs.clear()
        self.logger.error_logs.clear()
        self.logger.agent_activity.clear()
        
        return "🧹 **DEBUG LOGS CLEARED**\nAll performance metrics, error logs, and agent activity data have been cleared."


# Global debug instance (initialized by the main assistant)
_debug_logger: Optional[DnDAssistantLogger] = None
_health_monitor: Optional[SystemHealthMonitor] = None
_debug_commands: Optional[DebugCommands] = None


def initialize_debug_system(log_level: str = "INFO") -> tuple[DnDAssistantLogger, SystemHealthMonitor, DebugCommands]:
    """Initialize the global debug system"""
    global _debug_logger, _health_monitor, _debug_commands
    
    _debug_logger = DnDAssistantLogger(log_level)
    _health_monitor = SystemHealthMonitor(_debug_logger)
    _debug_commands = DebugCommands(_debug_logger, _health_monitor)
    
    return _debug_logger, _health_monitor, _debug_commands


def get_debug_logger() -> Optional[DnDAssistantLogger]:
    """Get the global debug logger"""
    return _debug_logger


def get_health_monitor() -> Optional[SystemHealthMonitor]:
    """Get the global health monitor"""
    return _health_monitor


def get_debug_commands() -> Optional[DebugCommands]:
    """Get the global debug commands"""
    return _debug_commands