class UIRegistry:

  def __init__(self):
    self._registry: dict[str, View] = {}

  def register(self, module, name):
    view = View(module, name)

    self._registry[view.key] = view

  def get(self, module, name) -> View:
    key = f"{module}.{name}"

    view = self._registry.get(key)

    if not view:
      raise ValueError(f"UI template '{key}' is not registered.")

    return view

  def list_registered(self):
    return list(self._registry.keys())


class View:
  def __init__(self, module, name):
    self.module = module
    self.name = name

  @property
  def key(self):
    return f"{self.module}.{self.name}"

  def path(self):
    return f"{self.module}/{self.name}.html"

  def load(self):
    raise NotImplementedError("Subclasses must implement the load method.")
