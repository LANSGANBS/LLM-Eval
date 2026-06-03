"""多线程管理模块 - 支持任务监控"""
import threading
import logging
from queue import Queue

logger = logging.getLogger(__name__)


class ThreadManager:
    """线程管理器 - 面向对象设计，支持任务队列"""
    
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.tasks = Queue()
        self.active_threads = []
        self.completed_tasks = []
        self._lock = threading.Lock()
        self._running = False
    
    def submit_task(self, func, *args, **kwargs):
        """提交任务到队列"""
        task_id = len(self.completed_tasks) + len(list(self.tasks.queue))
        task = {
            'id': task_id,
            'func': func,
            'args': args,
            'kwargs': kwargs,
            'status': 'pending',
            'result': None
        }
        self.tasks.put(task)
        logger.debug(f"任务 {task_id} 已提交")
        return task_id
    
    def start_workers(self):
        """启动工作线程"""
        self._running = True
        for _ in range(self.max_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self.active_threads.append(t)
    
    def _worker(self):
        """工作线程"""
        while self._running:
            try:
                task = self.tasks.get(timeout=1)
                task['status'] = 'running'
                try:
                    result = task['func'](*task['args'], **task['kwargs'])
                    task['result'] = result
                    task['status'] = 'completed'
                except Exception as e:
                    task['status'] = 'failed'
                    task['result'] = str(e)
                    logger.error(f"任务 {task['id']} 失败: {e}")
                finally:
                    with self._lock:
                        self.completed_tasks.append(task)
                    self.tasks.task_done()
            except:
                continue
    
    def get_task_status(self, task_id):
        """获取任务状态"""
        for task in self.completed_tasks:
            if task['id'] == task_id:
                return task
        for task in list(self.tasks.queue):
            if task['id'] == task_id:
                return task
        return None
    
    def get_all_status(self):
        """获取所有任务状态"""
        return {
            'pending': len(list(self.tasks.queue)),
            'completed': len([t for t in self.completed_tasks if t['status'] == 'completed']),
            'failed': len([t for t in self.completed_tasks if t['status'] == 'failed'])
        }
    
    def stop(self):
        """停止所有工作线程"""
        self._running = False
        for t in self.active_threads:
            t.join(timeout=2)
