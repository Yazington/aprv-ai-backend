# import cProfile
# import pstats


# def profile_route(func):
#     def wrapper(*args, **kwargs):
#         profiler = cProfile.Profile()
#         profiler.enable()
#         result = func(*args, **kwargs)
#         profiler.disable()
#         stats = pstats.Stats(profiler)
#         stats.strip_dirs().sort_stats("cumulative").print_stats(10)  # Adjust to show top N functions
#         return result

#     return wrapper
