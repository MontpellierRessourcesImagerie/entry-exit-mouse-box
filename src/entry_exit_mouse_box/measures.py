from concurrent.futures import ThreadPoolExecutor
import threading
import cv2
import numpy as np
import time
import os
from skimage.measure import regionprops

N_THREADS = int(min(4, os.cpu_count() // 2))
print(f"Using {N_THREADS} threads.")

class MiceVisibilityProcessor(object):
    """
    Calculates an array indicating for each box (designated by the labels in 'areas') if a mouse is inside or not.
    The process is realized on several threads.
    The input video was saved as a mask (0=BG, 255=FG) but it requires thresholding anyway due to compression.
    The areas are a grayscale image with one value per box (0=BG).
    To process the presence of a mouse, we use the length of the ellipse fitted to the mouse's label.
    It requires the input image to be calibrated.
    The process doesn't start from the frame 0 but from the frame 'start'.
    We don't need a control structure to write in the buffer as the threads are not writing in the same place.
    """
    def __init__(self, mask_path, areas, ma, start, duration):
        self.video_path      = mask_path
        self.track_duration  = int(duration)
        self.video_stream    = cv2.VideoCapture(mask_path)
        self.lock            = threading.Lock()
        self.labeled_boxes   = areas
        self.n_frames        = int(self.video_stream.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps             = self.video_stream.get(cv2.CAP_PROP_FPS)
        self.box_ids         = set([int(i) for i in np.unique(self.labeled_boxes) if int(i) != 0])
        self.current_frame   = 0
        self.min_trk_length  = ma
        self.starting_frames = {k: v+1 for k, v in start.items()}
        self.ranges          = self.split_frame_ranges(N_THREADS, self.n_frames)
        
        print(f"Total frames: {self.n_frames}")
        print(f"FPS: {self.fps}")
        print(f"Boxes: {self.box_ids}")
        print(f"Starters: {self.starting_frames}")

        self.instant_visibility = np.zeros((len(self.box_ids), self.n_frames), np.int8)
        self.instant_centroids  = np.zeros((self.n_frames, len(self.box_ids), 2), float)
        self.all_sessions       = None

        self.instant_centroids.fill(-1.0)
        self.video_stream.release()
        self.video_stream = None

    def process_visibility_pos(self, interval):
        video_stream = cv2.VideoCapture(self.video_path)
        video_stream.set(cv2.CAP_PROP_POS_FRAMES, interval[0])
        for i in range(interval[1] - interval[0]):
            _, frame = video_stream.read()
            mask  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) > 127
            mask  = mask.astype(np.float32)
            mask *= self.labeled_boxes
            mask  = mask.astype(np.uint8)
            all_props = regionprops(mask)
            for p in all_props:
                if p.label == 0:
                    continue
                l = int(p.label)
                y = int(p.centroid[0])
                x = int(p.centroid[1])
                self.instant_visibility[l-1, interval[0] + i] = 1
                self.instant_centroids[interval[0] + i, l-1]  = (y, x)
                # Export both arrays on the disk
        video_stream.release()

    def worker(self, thread_id):
        self.process_visibility_pos(self.ranges[thread_id])

    def get_session_length(self, box_rank, i1, i2):
        """
        Returns the distance traveled by the mouse during the session.
        Uses the sum of the distances between consecutive centroids.
        """
        if i1 == i2:
            return 0.0
        points = self.instant_centroids[i1:i2, box_rank]
        distance = 0.0
        for i in range(len(points)-1):
            distance += np.linalg.norm(points[i+1] - points[i])
        return distance

    def smooth_centroids(self, window_size=5):
        smoothed = np.full_like(self.instant_centroids, np.nan, dtype=np.float32)
        N = self.instant_centroids.shape[0]
        for box_rank in range(len(self.box_ids)):
            half_w = window_size // 2
            for i in range(N):
                start = max(0, i - half_w)
                end = min(N, i + half_w + 1)
                window = self.instant_centroids[start:end, box_rank]
                valid = (window >= 0).all(axis=1)
                if valid.any():
                    smoothed[i, box_rank] = window[valid].mean(axis=0)
                else:
                    smoothed[i, box_rank] = self.instant_centroids[i, box_rank]
        self.instant_centroids = smoothed

    def filter_visibility(self):
        for box_rank in range(len(self.box_ids)):
            swaps = []
            first_frame = self.starting_frames[box_rank+1] - 1
            last_frame_idx = min(first_frame + self.track_duration, self.n_frames)
            for f in range(self.n_frames-1):
                if f < first_frame:
                    self.instant_visibility[box_rank, f] = -1
                    self.instant_centroids[f, box_rank] = (-1.0, -1.0)
                    continue
                if f >= last_frame_idx:
                    self.instant_visibility[box_rank, f] = -2
                    self.instant_centroids[f, box_rank] = (-1.0, -1.0)
                    continue
                # State transition, the next session starts at (f+1)
                if (self.instant_visibility[box_rank, f] != self.instant_visibility[box_rank, f+1]) or (f == last_frame_idx-1):
                    # First transition: we don't care about the duration of the session
                    if len(swaps) == 0:
                        swaps.append(f+1)
                        continue
                    # We are in an unstable state.
                    if (self.get_session_length(box_rank, swaps[-1], f) < self.min_trk_length):
                        swaps.append(f+1)
                    else:
                        for i in range(swaps[0], swaps[-1]):
                            self.instant_visibility[box_rank, i] = 0
                            self.instant_centroids[i, box_rank] = (-1.0, -1.0)
                        swaps = [f+1]
        np.save("/tmp/visibility-02.npy", self.instant_visibility)
        np.save("/tmp/centroids-02.npy", self.instant_centroids)

    def split_frame_ranges(self, n_threads, n_frames):
        ranges = []
        base = n_frames // n_threads
        remainder = n_frames % n_threads

        start = 0
        for i in range(n_threads):
            end = start + base + (1 if i < remainder else 0)
            ranges.append((start, end))
            start = end

        return ranges

    def start_processing(self, num_workers=N_THREADS):
        print("(1/3) Processing visibility...")
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(self.worker, i) for i in range(num_workers)]
            for future in futures:
                future.result()
        print("(2/3) Processing number of in/out...")
        self.smooth_centroids()
        self.filter_visibility()
        print("(3/3) Processing sessions time and distance...")
        self.process_sessions()
        np.save("/tmp/visibility-03.npy", self.instant_visibility)
        np.save("/tmp/centroids-03.npy", self.instant_centroids)
    
    def process_sessions(self):
        """
        We call 'session' the span of time during which the mouse is hidden or visible.
        For each box, a video is a succession of sessions, alternating between hidden and visible.
        During a session, the mouse is either hidden or visible.
        A session is defined by a duration (in seconds) and a distance (in pixels).
        """
        self.all_sessions = {}
        for box in range(len(self.box_ids)):
            sessions = []
            count    = 0
            start    = 0
            for f in range(self.n_frames-1):
                state = (self.instant_visibility[box, f], self.instant_visibility[box, f+1])
                if (state[0] == state[1]):
                    continue
                # cases: (-1, 0), (-1, 1), (0, 1), (1, 0), (1, -2), (0, -2)
                if state[0] == -1: # Track's starting
                    start = f+2
                else:
                    count += 1
                    sessions.append({
                        'start'    : start,
                        'end'      : f + 1,
                        'duration' : f - start + 1,
                        'distance' : float(self.get_session_length(box, start-1, f+1)),
                        'status'   : int(state[0])
                    })
                    start = f + 2
                if state[1] == -2: # end of this track
                    self.all_sessions[box] = {
                        'sessions': sessions,
                        'count'   : count
                    }
                    break


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


from qtpy.QtCore import QThread, QObject, QTimer, Qt, Signal, Slot
from PyQt5.QtCore import pyqtSignal


class QtWorkerMVP(QObject):

    measures_ready = pyqtSignal(np.ndarray, np.ndarray, dict)

    def __init__(self, mask_path, areas, ma, start, duration):
        super().__init__()
        self.mask_path  = mask_path
        self.areas      = areas
        self.min_length = ma
        self.start      = start
        self.duration   = duration

    def run(self):
        mvp = MiceVisibilityProcessor(self.mask_path, self.areas, self.min_length, self.start, self.duration)
        mvp.start_processing()

        visibility = mvp.instant_visibility
        all_sessions = mvp.all_sessions
        centroids = mvp.instant_centroids

        self.measures_ready.emit(visibility, centroids, all_sessions)



# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    

if __name__ == "__main__":
    import tifffile

    mask_path = "/media/benedetti/5B0AAEC37149070F/mice-videos/2084-2086-2104-2106-T0.tmp/mask.avi"
    start_f   = {
        1: 820
    }
    areas_path = "/media/benedetti/5B0AAEC37149070F/mice-videos/2084-2086-2104-2106-T0.tmp/labeled-areas.tif"
    areas = tifffile.imread(areas_path)
    scale = 1.17
    unit = "mm"

    start = time.time()
    mvp = MiceVisibilityProcessor(mask_path, areas, 55, start_f, int(5*60*59.617))
    print(mvp.ranges)
    mvp.start_processing()
    duration = time.time() - start
    print(f"{duration:.2f}, {N_THREADS}")

    from pprint import pprint
    sessions = mvp.all_sessions
    pprint(sessions)
    