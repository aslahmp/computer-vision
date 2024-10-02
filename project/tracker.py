import cv2
import numpy as np
import math
from scipy.signal import hann
from collections import deque
class DAT_TRACKER:
    def __init__(self, cfg):
        self.cfg = cfg
        self.scale_factor_ = 1.0
        self.prob_lut_ = None
        self.prob_lut_distractor_ = None
        self.prob_lut_masked_ = None
        self.adaptive_threshold_ = None
        self.target_pos_history_ = []
        self.target_sz_history_ = []

    def pos2rect(self, target_pos, target_sz, img_size):
        """Convert target position and size to rectangle."""
        x = int(target_pos[0] - target_sz[0] / 2)
        y = int(target_pos[1] - target_sz[1] / 2)
        return (x, y, int(target_sz[0]), int(target_sz[1]))

    def get_subwindow(self, img, target_pos, surr_sz):
        """Get subwindow around target position."""
        x1 = int(target_pos[0] - surr_sz[0] / 2)
        y1 = int(target_pos[1] - surr_sz[1] / 2)
        x2 = int(target_pos[0] + surr_sz[0] / 2)
        y2 = int(target_pos[1] + surr_sz[1] / 2)

        # Ensure the coordinates are within the image boundaries
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
        return img[y1:y2, x1:x2]

    def get_foreground_background_probs(self, surr_win, obj_rect_surr, num_bins, bin_mapping):
        """Placeholder function for getting foreground/background probabilities."""
        # This function needs to be implemented based on your tracking algorithm
        # For now, let's return a dummy probability map
        prob_map = np.zeros(surr_win.shape[:2], dtype=np.float32)
        return prob_map

    def get_adaptive_threshold(self, prob_map, obj_rect_surr):
        """Placeholder function for getting adaptive threshold."""
        # This function needs to be implemented based on your tracking algorithm
        # For now, let's return a dummy adaptive threshold
        return np.mean(prob_map)

    def tracker_dat_initialize(self, I, region):
        cx = region[0] + (region[2] - 1) / 2.0
        cy = region[1] + (region[3] - 1) / 2.0
        w = region[2]
        h = region[3]

        target_pos = (round(cx), round(cy))
        target_sz = (round(w), round(h))

        # Scale factor calculation
        diag = math.sqrt(target_sz[0] ** 2 + target_sz[1] ** 2)
        self.scale_factor_ = min(1.0, round(10.0 * self.cfg['img_scale_target_diagonal'] / diag) / 10.0)
        
        target_pos = (int(target_pos[0] * self.scale_factor_), int(target_pos[1] * self.scale_factor_))
        target_sz = (int(target_sz[0] * self.scale_factor_), int(target_sz[1] * self.scale_factor_))

        # Resize the input image
        img = cv2.resize(I, None, fx=self.scale_factor_, fy=self.scale_factor_)

        # Color space conversion based on configuration
        if self.cfg['color_space'] == 1:  # RGB
            img = img.copy()
        elif self.cfg['color_space'] == 2:  # LAB
            img = cv2.cvtColor(img, cv2.COLOR_BGR2Lab)
        elif self.cfg['color_space'] == 3:  # HSV
            img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        elif self.cfg['color_space'] == 4:  # Grayscale
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            print("color_space does not equal any of the above cases")

        # Create the surrounding window size
        surr_sz = (int(self.cfg['surr_win_factor'] * target_sz[0]),
                   int(self.cfg['surr_win_factor'] * target_sz[1]))

        surr_rect = self.pos2rect(target_pos, surr_sz, img.shape[:2])
        obj_rect_surr = self.pos2rect(target_pos, target_sz, img.shape[:2])

        # Adjust object rectangle based on the surrounding rectangle
        obj_rect_surr = (obj_rect_surr[0] - surr_rect[0], obj_rect_surr[1] - surr_rect[1],
                         obj_rect_surr[2], obj_rect_surr[3])

        # Get the subwindow of the image for tracking
        surr_win = self.get_subwindow(img, target_pos, surr_sz)

        # Get foreground and background probabilities
        prob_map = self.get_foreground_background_probs(surr_win, obj_rect_surr, 
                                                        self.cfg['num_bins'], self.cfg['bin_mapping'])

        # Clone the probability look-up tables (placeholders)
        self.prob_lut_distractor_ = self.prob_lut_.copy() if self.prob_lut_ is not None else None
        self.prob_lut_masked_ = self.prob_lut_.copy() if self.prob_lut_ is not None else None

        # Compute adaptive threshold based on the probability map
        self.adaptive_threshold_ = self.get_adaptive_threshold(prob_map, obj_rect_surr)

        # Save the target position and size history for tracking
        self.target_pos_history_.append((target_pos[0] / self.scale_factor_, target_pos[1] / self.scale_factor_))
        self.target_sz_history_.append((target_sz[0] / self.scale_factor_, target_sz[1] / self.scale_factor_))
    def get_foreground_prob(self, frame, prob_lut, bin_mapping):
        # Ensure the input image is 3-channel (RGB)
        if frame.shape[2] != 3:
            raise ValueError("Expected a 3-channel (RGB) image")

        # Ensure bin_mapping is 1D with 256 elements
        if bin_mapping.size != 256 or bin_mapping.ndim != 1:
            raise ValueError("bin_mapping must be a 1D array with 256 elements")

        # Apply bin mapping to each channel using cv2.LUT
        frame_bin = np.zeros_like(frame)
        for i in range(3):  # Iterate over each channel (B, G, R)
            frame_bin[:, :, i] = cv2.LUT(frame[:, :, i], bin_mapping)

        # Initialize the probability map
        prob_map = np.zeros(frame.shape[:2], dtype=np.float32)

        # Iterate over each pixel in the frame_bin
        height, width = frame.shape[:2]
        for y in range(height):
            for x in range(width):
                # Get the bin-mapped values for each pixel
                b, g, r = frame_bin[y, x]
                # Use the bin-mapped values to index into the prob_lut and fill the prob_map
                prob_map[y, x] = prob_lut[b, g, r]

        return prob_map
    def get_motion_prediction(self, values, max_num_frames):
        pred = np.array([0.0, 0.0])
        if len(values) < 3:
            pred[0] = 0
            pred[1] = 0
        else:
            max_num_frames += 2
            A1 = 0.8
            A2 = -1
            
            V = values[max(0, len(values) - max_num_frames):]
            P = []
            for i in range(2, len(V)):
                P.append(np.array([
                    A1 * (V[i][0] - V[i - 2][0]) + A2 * (V[i - 1][0] - V[i - 2][0]),
                    A1 * (V[i][1] - V[i - 2][1]) + A2 * (V[i - 1][1] - V[i - 2][1])
                ]))
            for p in P:
                pred += p
            pred /= len(P) if P else 1
        return tuple(pred)
    def tracker_dat_update(self, I):
            img_preprocessed = cv2.resize(I, None, fx=self.scale_factor_, fy=self.scale_factor_)
            img = None

            # Color space conversion based on configuration
            if self.cfg['color_space'] == 1:  # RGB
                img = img_preprocessed.copy()
            elif self.cfg['color_space'] == 2:  # LAB
                img = cv2.cvtColor(img_preprocessed, cv2.COLOR_BGR2Lab)
            elif self.cfg['color_space'] == 3:  # HSV
                img = cv2.cvtColor(img_preprocessed, cv2.COLOR_BGR2HSV)
            elif self.cfg['color_space'] == 4:  # Grayscale
                img = cv2.cvtColor(img_preprocessed, cv2.COLOR_BGR2GRAY)
            else:
                print("color_space does not equal any of the above cases")

            prev_pos = self.target_pos_history_[-1] if self.target_pos_history_ else (0, 0)
            prev_sz = self.target_sz_history_[-1] if self.target_sz_history_ else (0, 0)

            if self.cfg['motion_estimation_history_size'] > 0:
                motion_pred = self.get_motion_prediction(self.target_pos_history_, self.cfg['motion_estimation_history_size'])
                prev_pos = (prev_pos[0] + motion_pred[0], prev_pos[1] + motion_pred[1])

            target_pos = (prev_pos[0] * self.scale_factor_, prev_pos[1] * self.scale_factor_)
            target_sz = (prev_sz[0] * self.scale_factor_, prev_sz[1] * self.scale_factor_)

            # Calculate search size
            search_sz = (
                int(target_sz[0] + self.cfg['search_win_padding'] * max(target_sz)),
                int(target_sz[1] + self.cfg['search_win_padding'] * max(target_sz))
            )
            search_rect = self.pos2rect(target_pos, search_sz, img.shape[:2])
            search_win, padded_search_win = self.get_subwindow_masked(img, target_pos, search_sz)

            # Apply probability LUT
            pm_search = self.get_foreground_prob(search_win, self.prob_lut_, self.cfg['bin_mapping'])
            pm_search_dist = None

            if self.cfg['distractor_aware']:
                pm_search_dist = self.get_foreground_prob(search_win, self.prob_lut_distractor_, self.cfg['bin_mapping'])
                pm_search = (pm_search + pm_search_dist) / 2.0
            pm_search[padded_search_win == 0] = 0  # Masking

            # Calculate Cosine / Hanning window
            cos_win = hann(search_sz[0])[:, None] * hann(search_sz[1])

            hypotheses, vote_scores, dist_scores = self.get_nms_rects(pm_search, target_sz, self.cfg['nms_scale'], 
                                                                        self.cfg['nms_overlap'], self.cfg['nms_score_factor'], 
                                                                        cos_win, self.cfg['nms_include_center_vote'])

            candidate_centers = []
            candidate_scores = []
            for i in range(len(hypotheses)):
                center = (float(hypotheses[i][0] + hypotheses[i][2] / 2), float(hypotheses[i][1] + hypotheses[i][3] / 2))
                candidate_centers.append(center)
                candidate_scores.append(vote_scores[i] * dist_scores[i])

            best_candidate_index = np.argmax(candidate_scores)
            target_pos = candidate_centers[best_candidate_index]

            # Distractor processing
            distractors = []
            distractor_overlap = []
            if len(hypotheses) > 1:
                target_rect = self.pos2rect(target_pos, target_sz, pm_search.shape)
                for i in range(len(hypotheses)):
                    if i != best_candidate_index:
                        distractors.append(hypotheses[i])
                        overlap = self.intersection_over_union(target_rect, distractors[-1])
                        distractor_overlap.append(overlap)

            # Localization visualization
            if self.cfg['show_figures']:
                pm_search_color = (pm_search * 255).astype(np.uint8)
                pm_search_color = cv2.applyColorMap(pm_search_color, cv2.COLORMAP_JET)
                for i in range(len(hypotheses)):
                    color = (0, 255, 255 * (i != best_candidate_index))
                    cv2.rectangle(pm_search_color, hypotheses[i], color, 2)
                cv2.imshow("Search Window", pm_search_color)
                cv2.waitKey(1)

            # Appearance update
            target_pos_img = (target_pos[0] + search_rect[0], target_pos[1] + search_rect[1])
            if self.cfg['prob_lut_update_rate'] > 0:
                surr_sz = (
                    int(self.cfg['surr_win_factor'] * target_sz[0]),
                    int(self.cfg['surr_win_factor'] * target_sz[1])
                )
                surr_rect = self.pos2rect(target_pos_img, surr_sz, img.shape[:2])
                obj_rect_surr = self.pos2rect(target_pos_img, target_sz, img.shape[:2])

                obj_rect_surr = (obj_rect_surr[0] - surr_rect[0], obj_rect_surr[1] - surr_rect[1], obj_rect_surr[2], obj_rect_surr[3])
                surr_win = self.get_subwindow_masked(img, target_pos_img, surr_sz)[0]

                prob_lut_bg = self.get_foreground_prob(surr_win, self.prob_lut_, self.cfg['bin_mapping'])

                if self.cfg['distractor_aware']:
                    if len(distractors) > 1:
                        obj_rect = self.pos2rect(target_pos, target_sz, search_win.shape)
                        prob_lut_dist = self.get_foreground_prob(search_win, obj_rect, self.cfg['num_bins'])
                        self.prob_lut_distractor_ = (1 - self.cfg['prob_lut_update_rate']) * self.prob_lut_distractor_ + \
                                                    self.cfg['prob_lut_update_rate'] * prob_lut_dist
                    else:
                        self.prob_lut_distractor_ = (1 - self.cfg['prob_lut_update_rate']) * self.prob_lut_distractor_ + \
                                                    self.cfg['prob_lut_update_rate'] * prob_lut_bg

                    if not distractors or (max(distractor_overlap) < 0.1):
                        self.prob_lut_ = (1 - self.cfg['prob_lut_update_rate']) * self.prob_lut_ + \
                                        self.cfg['prob_lut_update_rate'] * prob_lut_bg
    def intersection_over_union(self, target_rect, candidates):
        intersection_area = (target_rect & candidates).area()
        return float(intersection_area) / float(target_rect.area() + candidates.area() - intersection_area)
    def get_subwindow_masked(self, im, pos, sz):
        xs_1 = int(np.floor(pos[0])) + 1 - int(np.floor(sz[0] / 2.))
        xs_2 = int(np.floor(pos[0])) + sz[0] - int(np.floor(sz[0] / 2.))
        ys_1 = int(np.floor(pos[1])) + 1 - int(np.floor(sz[1] / 2.))
        ys_2 = int(np.floor(pos[1])) + sz[1] - int(np.floor(sz[1] / 2.))

        out = self.get_subwindow(im, pos, sz)

        bbox = (xs_1, ys_1, sz[0], sz[1])
        bbox = (max(bbox[0], 0), max(bbox[1], 0), min(bbox[0] + bbox[2], im.shape[1] - 1), min(bbox[1] + bbox[3], im.shape[0] - 1))
        bbox = (bbox[0] - xs_1, bbox[1] - ys_1, bbox[2], bbox[3])
        
        mask = np.ones(sz, dtype=np.uint8)
        mask[bbox[1]:bbox[1]+bbox[3], bbox[0]:bbox[0]+bbox[2]] = 0
        return out, mask

    # def get_subwindow(self, frame, center_coor, sz):
    #     lefttop_x = max(0, min(frame.shape[1] - 1, center_coor[0] - sz[0] // 2))
    #     lefttop_y = max(0, min(frame.shape[0] - 1, center_coor[1] - sz[1] // 2))
    #     rightbottom_x = lefttop_x + sz[0]
    #     rightbottom_y = lefttop_y + sz[1]

    #     border = (max(0, -lefttop_x), max(0, -lefttop_y), max(0, rightbottom_x - frame.shape[1]), max(0, rightbottom_y - frame.shape[0]))
    #     lefttop_limit = (max(lefttop_x, 0), max(lefttop_y, 0))
    #     rightbottom_limit = (min(rightbottom_x, frame.shape[1]), min(rightbottom_y, frame.shape[0]))

    #     sub_window = frame[lefttop_limit[1]:rightbottom_limit[1], lefttop_limit[0]:rightbottom_limit[0]].copy()

    #     if any(border):
    #         sub_window = cv2.copyMakeBorder(sub_window, border[1], border[3], border[0], border[2], cv2.BORDER_REPLICATE)
    #     return sub_window